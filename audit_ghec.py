#!/usr/bin/env python3
"""
================================================================================
GitHub Enterprise Cloud (GHEC) Read-Only Configuration & Policy Auditor (Python)
================================================================================

PURPOSE:
    Audits and records all readable GitHub Enterprise Cloud (GHEC) settings
    across both the Enterprise level and every child Organization.

READ-ONLY GUARANTEE:
    - REST API calls exclusively use HTTP GET (`method="GET"`).
    - GraphQL API calls enforce that the query string starts with `query`
      (GraphQL mutations are explicitly blocked).
    - No settings, repositories, memberships, or tokens are modified.

OUTPUT STRUCTURE:
    ghec-audit-<enterprise>-<timestamp>/
    ├── AUDIT_SUMMARY.md                       # Human-readable Markdown report
    ├── enterprise/
    │   ├── 01-policies-and-identity.json      # GraphQL policies, SAML, domains, SSH CAs
    │   ├── 02-ip-allow-list.json              # Paginated Enterprise IP allow list CIDRs
    │   ├── 03-enterprise-admins.json          # Paginated Enterprise Owners & Billing Mgrs
    │   ├── 04-organizations-list.json         # Complete list of child Organizations
    │   ├── 99-recent-config-audit-log.json    # Recent config changes from Enterprise Audit Log
    │   ├── <rest-endpoint>.json               # Enterprise Actions, Copilot, Billing, GHAS
    │   └── rulesets/ruleset-<id>.json         # Full rule definitions per Enterprise ruleset
    └── orgs/
        └── <org-login>/
            ├── 01-general-settings.json       # Core Org settings (2FA, base perms, GHAS)
            ├── <rest-endpoint>.json           # Actions, secrets metadata, apps, hooks, roles
            ├── rulesets/ruleset-<id>.json     # Full rule definitions per Org ruleset
            └── security-configs/config-<id>.json # Full GHAS security preset details

USAGE:
    python3 audit_ghec.py <enterprise-slug> [--workers 16] [--token <pat>]
================================================================================
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional


# ==============================================================================
# SECTION 1: API CONSTANTS, GRAPHQL QUERIES, & ENDPOINT DEFINITIONS
# ==============================================================================

API_BASE = "https://api.github.com"

# GraphQL query to retrieve Enterprise-wide member privileges, repository policies,
# SAML Single Sign-On settings, verified domains, and SSH Certificate Authorities.
ENTERPRISE_GRAPHQL_QUERY = """
query($slug: String!) {
  enterprise(slug: $slug) {
    name
    slug
    url
    createdAt
    # Enterprise license and storage consumption metrics
    billingInfo {
      allLicensableUsersCount
      assetPacks
      bandwidthQuota
      bandwidthUsage
      storageQuota
      storageUsage
    }
    ownerInfo {
      # --- Repository & Member Privilege Policies ---
      defaultRepositoryPermissionSetting
      membersCanCreateRepositoriesSetting
      membersCanCreatePublicRepositoriesSetting
      membersCanCreatePrivateRepositoriesSetting
      membersCanCreateInternalRepositoriesSetting
      membersCanDeleteRepositoriesSetting
      membersCanDeleteIssuesSetting
      membersCanInviteCollaboratorsSetting
      membersCanMakePurchasesSetting
      membersCanUpdateProtectedBranchesSetting
      membersCanViewDependencyInsightsSetting
      membersCanChangeRepositoryVisibilitySetting
      organizationProjectsSetting
      repositoryProjectsSetting
      teamDiscussionsSetting

      # --- Authentication, Network, & Notification Security Policies ---
      twoFactorRequiredSetting
      ipAllowListEnabledSetting
      ipAllowListForInstalledAppsEnabledSetting
      notificationDeliveryRestrictionEnabledSetting

      # --- SAML Single Sign-On (SSO) Identity Provider Configuration ---
      samlIdentityProvider {
        ssoUrl
        issuer
        digestMethod
        signatureMethod
      }
    }
  }
}
"""

# Enterprise-level REST API endpoints (/enterprises/{enterprise}/...)
# Each entry maps to a specific policy area in the GHEC Enterprise Settings UI.
ENTERPRISE_ENDPOINTS = [
    "actions/permissions",                        # Actions enablement & allowed actions policy
    "actions/permissions/organizations",          # Which orgs are permitted to run GitHub Actions
    "actions/permissions/selected-actions",       # Allowed marketplace/verified actions & patterns
    "actions/permissions/workflow",               # Default GITHUB_TOKEN permissions & PR approval toggle
    "actions/permissions/artifact-and-log-retention",  # Enterprise log & artifact retention days
    "actions/runner-groups",                      # Self-hosted & GitHub-hosted Enterprise runner groups
    "actions/runners",                            # Enterprise-level self-hosted runners inventory
    "actions/cache/usage-policy",                 # Actions cache storage limit policies
    "code-security/configurations",               # Enterprise GitHub Advanced Security (GHAS) presets
    "copilot/billing",                            # Enterprise Copilot seat management & billing summary
    "rulesets",                                   # Enterprise-wide repository/branch/tag rulesets list
    "settings/billing/actions",                   # Actions minutes usage breakdown
    "settings/billing/packages",                  # GitHub Packages bandwidth usage breakdown
    "settings/billing/shared-storage",            # Shared Actions/Packages storage usage
    "settings/billing/cost-centers",              # Enterprise billing cost centers configuration
    "team-sync/idp-mappings",                     # IdP group-to-team synchronization mappings
]

# Organization-level REST API endpoints (/orgs/{org}/...)
# Audited for every organization discovered inside the Enterprise.
ORG_ENDPOINTS = [
    "actions/permissions",                        # Org Actions enablement & allowed actions policy
    "actions/permissions/repositories",           # Repositories permitted to use Actions in the Org
    "actions/permissions/selected-actions",       # Org-level allowed actions whitelist patterns
    "actions/permissions/workflow",               # Org default GITHUB_TOKEN permissions & PR approvals
    "actions/permissions/artifact-and-log-retention",  # Org artifact & log retention days
    "actions/runner-groups",                      # Org runner groups & repository access rules
    "actions/runners",                            # Org self-hosted runners inventory
    "actions/secrets",                            # Org Actions Secrets METADATA only (names/visibility; never values)
    "actions/variables",                          # Org Actions configuration variables
    "codespaces/access",                          # Who can use Codespaces & billable owner limits
    "codespaces/secrets",                         # Org Codespaces Secrets METADATA only
    "copilot/billing",                            # Org Copilot seat assignment & policy settings
    "dependabot/secrets",                         # Org Dependabot Secrets METADATA only
    "hooks",                                      # Organization-wide webhooks & delivery settings
    "installations",                              # Installed GitHub Apps & granted permissions
    "interaction-limits",                         # Temporary interaction restrictions (if active)
    "organization-roles",                         # Custom Organization Roles definitions
    "personal-access-token-requests",             # Pending Fine-Grained PAT approval requests
    "fine-grained-personal-access-tokens",        # Approved Fine-Grained PATs accessing the Org
    "properties/schema",                          # Custom Repository Properties schema definitions
    "rulesets",                                   # Organization-level branch/tag rulesets list
    "code-security/configurations",               # Organization-level GHAS security configurations
    "security-managers",                          # Teams granted the Security Manager role
    "settings/billing/actions",                   # Org Actions billing usage
    "settings/billing/packages",                  # Org Packages billing usage
    "settings/billing/shared-storage",            # Org shared storage usage
    "team-sync/idp-mappings",                     # Org IdP team synchronization mappings
]


# ==============================================================================
# SECTION 2: AUTHENTICATION & TOKEN RESOLUTION
# ==============================================================================

def get_token(explicit_token: Optional[str]) -> str:
    """
    Resolves the GitHub authentication token in priority order:
      1. `--token` CLI argument
      2. `GITHUB_TOKEN` environment variable
      3. Active GitHub CLI (`gh auth token`) session
    """
    if explicit_token:
        return explicit_token
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        res = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=True
        )
        return res.stdout.strip()
    except Exception:
        sys.exit(
            "Error: No GitHub token found. Set GITHUB_TOKEN, pass --token, or run `gh auth login`."
        )


# ==============================================================================
# SECTION 3: READ-ONLY AUDITOR ENGINE (HTTP POOLING & PAGINATION)
# ==============================================================================

class ReadOnlyGitHubAuditor:
    """
    Executes concurrent, strictly read-only queries against GitHub's GraphQL
    and REST APIs, persisting raw JSON evidence and a Markdown summary report.
    """

    def __init__(self, token: str, out_dir: Path, workers: int = 16):
        self.out_dir = out_dir
        self.workers = workers
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "GHEC-ReadOnly-Auditor-Python",
        }

        # Attempt to use `requests.Session` for persistent HTTP Keep-Alive
        # connection pooling across worker threads; falls back to Python stdlib
        # `urllib.request` if `requests` is not installed.
        self.session = None
        try:
            import requests
            from requests.adapters import HTTPAdapter

            self.session = requests.Session()
            self.session.headers.update(self.headers)
            adapter = HTTPAdapter(pool_connections=workers, pool_maxsize=workers * 2)
            self.session.mount("https://", adapter)
        except ImportError:
            pass

    def _http_get(self, url: str) -> tuple[int, Any, Dict[str, str]]:
        """
        Executes a strictly Read-Only HTTP GET request.
        Automatically inspects `X-RateLimit-Remaining` and backs off if rate-limited.
        """
        for _attempt in range(3):
            if self.session is not None:
                resp = self.session.get(url, timeout=30)
                status = resp.status_code
                headers = dict(resp.headers)
                # Handle primary or secondary rate limits gracefully
                if status == 429 or (
                    status == 403 and headers.get("X-RateLimit-Remaining") == "0"
                ):
                    reset = int(headers.get("X-RateLimit-Reset", time.time() + 5))
                    sleep_for = max(1, reset - int(time.time()))
                    time.sleep(min(sleep_for, 60))
                    continue
                if status >= 400:
                    return status, None, headers
                return status, resp.json(), headers
            else:
                req = urllib.request.Request(url, headers=self.headers, method="GET")
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        return resp.status, data, dict(resp.headers)
                except urllib.error.HTTPError as e:
                    if e.code in (403, 429) and e.headers.get("X-RateLimit-Remaining") == "0":
                        time.sleep(5)
                        continue
                    return e.code, None, {}
                except Exception:
                    return 500, None, {}
        return 500, None, {}

    def fetch_rest_paginated(self, path: str, outfile: Path) -> Optional[Any]:
        """
        Fetches a GitHub REST API endpoint using GET and automatically follows
        RFC 5988 `Link: <...>; rel="next"` pagination headers until all pages
        are collected. Saves the combined JSON output to `outfile`.
        """
        sep = "&" if "?" in path else "?"
        next_url: Optional[str] = f"{API_BASE}{path}{sep}per_page=100"
        accumulated: List[Any] = []
        is_list = False

        while next_url:
            status, data, headers = self._http_get(next_url)
            # If an endpoint returns 404/403 (e.g., feature not enabled or no access),
            # skip writing an empty/error file.
            if status >= 400 or data is None:
                return None

            if isinstance(data, list):
                is_list = True
                accumulated.extend(data)
            else:
                # Single JSON object response (e.g., /orgs/{org} or /actions/permissions)
                outfile.parent.mkdir(parents=True, exist_ok=True)
                outfile.write_text(json.dumps(data, indent=2), encoding="utf-8")
                return data

            # Parse the `Link` response header to check if another page exists
            link = headers.get("Link") or headers.get("link") or ""
            match = re.search(r'<([^>]+)>;\s*rel="next"', link)
            next_url = match.group(1) if match else None

        if is_list:
            outfile.parent.mkdir(parents=True, exist_ok=True)
            outfile.write_text(json.dumps(accumulated, indent=2), encoding="utf-8")
            return accumulated
        return None

    def fetch_graphql(
        self, query: str, variables: Dict[str, Any], outfile: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Executes a read-only GraphQL `query` operation.
        Explicitly refuses to execute if the operation is not a `query` (blocks mutations).
        """
        if not query.lstrip().startswith("query"):
            raise ValueError("Security Block: Refusing to run non-query GraphQL operation.")

        payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        if self.session is not None:
            resp = self.session.post(f"{API_BASE}/graphql", data=payload, timeout=30)
            data = resp.json()
        else:
            headers = {**self.headers, "Content-Type": "application/json"}
            req = urllib.request.Request(
                f"{API_BASE}/graphql", data=payload, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

        if outfile:
            outfile.parent.mkdir(parents=True, exist_ok=True)
            outfile.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    def fetch_graphql_paginated_nodes(
        self, slug: str, field_query: str, extract_fn, outfile: Path
    ) -> List[Any]:
        """
        Walks cursor-based GraphQL pagination (`first: 100, after: $endCursor`)
        until `pageInfo.hasNextPage` is False, combining all nodes into `outfile`.
        Safely returns an empty list if the parent GraphQL object is null/inaccessible.
        """
        nodes: List[Any] = []
        cursor: Optional[str] = None
        while True:
            data = self.fetch_graphql(
                field_query, {"slug": slug, "endCursor": cursor}
            )
            if not isinstance(data, dict) or not (data.get("data") or {}).get("enterprise"):
                break
            try:
                page_nodes, page_info = extract_fn(data)
            except (KeyError, TypeError):
                break
            if page_nodes:
                nodes.extend(page_nodes)
            if not isinstance(page_info, dict) or not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        outfile.parent.mkdir(parents=True, exist_ok=True)
        outfile.write_text(json.dumps(nodes, indent=2), encoding="utf-8")
        return nodes

    def discover_viewer_context(self) -> tuple[List[str], List[str], str]:
        """
        Queries the authenticated user's Enterprises and Organizations via GraphQL
        and REST `/user/orgs` when the provided slug is a username or invalid.
        Returns (enterprise_slugs, org_logins, viewer_login).
        """
        viewer_query = """
        query {
          viewer {
            login
            enterprises(first: 50) {
              nodes { slug name }
            }
            organizations(first: 100) {
              nodes { login }
            }
          }
        }"""
        ent_slugs: List[str] = []
        org_logins: List[str] = []
        viewer_login = ""
        try:
            res = self.fetch_graphql(viewer_query, {})
            viewer = (res.get("data") or {}).get("viewer") or {}
            viewer_login = viewer.get("login", "")
            for ent in ((viewer.get("enterprises") or {}).get("nodes") or []):
                if ent and ent.get("slug"):
                    ent_slugs.append(ent["slug"])
            for org in ((viewer.get("organizations") or {}).get("nodes") or []):
                if org and org.get("login"):
                    org_logins.append(org["login"])
        except Exception:
            pass

        # Also check REST `/user/orgs` in case GraphQL lacked `read:enterprise` scope
        status, rest_orgs, _ = self._http_get(f"{API_BASE}/user/orgs?per_page=100")
        if status == 200 and isinstance(rest_orgs, list):
            for o in rest_orgs:
                if isinstance(o, dict) and o.get("login") and o["login"] not in org_logins:
                    org_logins.append(o["login"])

        return ent_slugs, org_logins, viewer_login

    # ==========================================================================
    # SECTION 4: ENTERPRISE-LEVEL AUDIT (GRAPHQL + REST + AUDIT LOG)
    # ==========================================================================

    def audit_enterprise(self, enterprise: str) -> List[str]:
        """
        Audits all Enterprise-level policies, identity settings, IP allow lists,
        admins, REST endpoints, ruleset details, and recent Audit Log config events.
        If `enterprise` is not a valid GHEC Enterprise slug (e.g., a username or org),
        auto-discovers the user's Enterprises and Organizations and falls back cleanly.
        """
        ent_dir = self.out_dir / "enterprise"
        (ent_dir / "rulesets").mkdir(parents=True, exist_ok=True)

        # --- Step 1A: Enterprise Policies & SAML Identity ---
        print(f"[1/4] Fetching Enterprise GraphQL policies & identity for '{enterprise}'...")
        pol_res = self.fetch_graphql(
            ENTERPRISE_GRAPHQL_QUERY,
            {"slug": enterprise},
            ent_dir / "01-policies-and-identity.json",
        )

        # Check if the slug resolved to an accessible GHEC Enterprise
        if not ((pol_res.get("data") or {}).get("enterprise")):
            errors = pol_res.get("errors") or []
            err_msg = errors[0].get("message", "Unknown error") if errors else "Enterprise returned null"
            print(f"\n[!] Note: Could not resolve Enterprise slug '{enterprise}' ({err_msg}).")
            print("    -> Auto-discovering Enterprises and Organizations accessible to your token...")

            ent_slugs, viewer_orgs, viewer_login = self.discover_viewer_context()
            if ent_slugs and enterprise not in ent_slugs:
                real_ent = ent_slugs[0]
                print(f"    -> Found Enterprise(s) on account '{viewer_login}': {', '.join(ent_slugs)}")
                print(f"    -> Switching target Enterprise slug to '{real_ent}'...")
                enterprise = real_ent
                self.fetch_graphql(
                    ENTERPRISE_GRAPHQL_QUERY,
                    {"slug": enterprise},
                    ent_dir / "01-policies-and-identity.json",
                )
            else:
                if not ent_slugs:
                    print(
                        f"    -> Account '{viewer_login or enterprise}' has no visible GHEC Enterprise "
                        "(or token lacks `read:enterprise` scope: `gh auth refresh -h github.com -s read:enterprise,admin:enterprise,read:org`)."
                    )
                if viewer_orgs:
                    print(f"    -> Falling back to auditing your {len(viewer_orgs)} accessible Organization(s): {', '.join(viewer_orgs)}")
                    (ent_dir / "04-organizations-list.json").write_text(
                        json.dumps([{"login": o} for o in viewer_orgs], indent=2), encoding="utf-8"
                    )
                    return viewer_orgs
                else:
                    # Check if the argument itself is an Organization login
                    st, org_check, _ = self._http_get(f"{API_BASE}/orgs/{enterprise}")
                    if st == 200 and isinstance(org_check, dict) and org_check.get("login"):
                        print(f"    -> '{enterprise}' is a GitHub Organization (not an Enterprise). Auditing Organization '{enterprise}'...")
                        return [enterprise]
                    print("    -> No Enterprises or Organizations found for this account.")
                    return []

        # --- Step 1B: Paginated Enterprise IP Allow List Entries ---
        ip_query = """
        query($slug: String!, $endCursor: String) {
          enterprise(slug: $slug) {
            ownerInfo {
              ipAllowListEntries(first: 100, after: $endCursor) {
                pageInfo { hasNextPage endCursor }
                nodes { name allowListValue isActive createdAt updatedAt }
              }
            }
          }
        }"""
        try:
            self.fetch_graphql_paginated_nodes(
                enterprise,
                ip_query,
                lambda d: (
                    d["data"]["enterprise"]["ownerInfo"]["ipAllowListEntries"]["nodes"],
                    d["data"]["enterprise"]["ownerInfo"]["ipAllowListEntries"]["pageInfo"],
                ),
                ent_dir / "02-ip-allow-list.json",
            )
        except Exception:
            pass

        # --- Step 1C: Paginated Enterprise Owners & Billing Managers ---
        admin_query = """
        query($slug: String!, $endCursor: String) {
          enterprise(slug: $slug) {
            ownerInfo {
              admins(first: 100, after: $endCursor) {
                pageInfo { hasNextPage endCursor }
                edges { role node { login name email } }
              }
            }
          }
        }"""
        try:
            self.fetch_graphql_paginated_nodes(
                enterprise,
                admin_query,
                lambda d: (
                    d["data"]["enterprise"]["ownerInfo"]["admins"]["edges"],
                    d["data"]["enterprise"]["ownerInfo"]["admins"]["pageInfo"],
                ),
                ent_dir / "03-enterprise-admins.json",
            )
        except Exception:
            pass

        # --- Step 1D: Paginated Discovery of All Child Organizations ---
        org_query = """
        query($slug: String!, $endCursor: String) {
          enterprise(slug: $slug) {
            organizations(first: 100, after: $endCursor) {
              pageInfo { hasNextPage endCursor }
              nodes { login }
            }
          }
        }"""
        org_nodes = self.fetch_graphql_paginated_nodes(
            enterprise,
            org_query,
            lambda d: (
                d["data"]["enterprise"]["organizations"]["nodes"],
                d["data"]["enterprise"]["organizations"]["pageInfo"],
            ),
            ent_dir / "04-organizations-list.json",
        )
        orgs = [n["login"] for n in org_nodes if n and "login" in n]

        # --- Step 2: Concurrent Enterprise REST Endpoints ---
        print("[2/4] Fetching Enterprise REST endpoints concurrently...")
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {
                pool.submit(
                    self.fetch_rest_paginated,
                    f"/enterprises/{enterprise}/{ep}",
                    ent_dir / f"{ep.replace('/', '-')}.json",
                ): ep
                for ep in ENTERPRISE_ENDPOINTS
            }
            for f in as_completed(futures):
                f.result()

            # Deep-inspect each Enterprise Ruleset by ID (list endpoint only has summaries)
            rs_file = ent_dir / "rulesets.json"
            if rs_file.exists():
                rulesets = json.loads(rs_file.read_text(encoding="utf-8"))
                rs_futures = [
                    pool.submit(
                        self.fetch_rest_paginated,
                        f"/enterprises/{enterprise}/rulesets/{rs['id']}",
                        ent_dir / "rulesets" / f"ruleset-{rs['id']}.json",
                    )
                    for rs in (rulesets if isinstance(rulesets, list) else [])
                    if isinstance(rs, dict) and "id" in rs
                ]
                for f in as_completed(rs_futures):
                    f.result()

        # --- Step 3: Enterprise Audit Log for Config & UI-Only Toggles ---
        print("[3/4] Fetching recent Enterprise configuration change events from Audit Log...")
        self.fetch_rest_paginated(
            f"/enterprises/{enterprise}/audit-log?phrase=action:enterprise+action:org.config+action:copilot+action:codespaces+action:hook+action:ip_allow_list",
            ent_dir / "99-recent-config-audit-log.json",
        )

        return orgs

    # ==========================================================================
    # SECTION 5: ORGANIZATION-LEVEL LOOP & DEEP INSPECTION
    # ==========================================================================

    def _build_org_tasks(self, org: str) -> List[tuple[str, Path]]:
        """
        Builds the list of (REST endpoint path, output JSON file path) tuples
        to fetch for a single Organization.
        """
        org_dir = self.out_dir / "orgs" / org
        tasks = [(f"/orgs/{org}", org_dir / "01-general-settings.json")]
        for ep in ORG_ENDPOINTS:
            safe_name = ep.replace("/", "-")
            tasks.append((f"/orgs/{org}/{ep}", org_dir / f"{safe_name}.json"))
        return tasks

    def audit_organizations(self, orgs: List[str]) -> None:
        """
        Loops through all discovered Organizations and concurrently fetches:
          1. General organization settings (/orgs/{org})
          2. All 27 secondary organization endpoints (Actions, secrets metadata, apps, etc.)
          3. Full rule definitions for every Organization Ruleset
          4. Full details for every Organization Code Security (GHAS) Configuration
        """
        print(f"[4/4] Auditing {len(orgs)} Organizations with {self.workers} threads...")
        all_tasks: List[tuple[str, Path]] = []
        for org in orgs:
            all_tasks.extend(self._build_org_tasks(org))

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            # Execute all primary Org endpoint requests across the thread pool
            futures = [
                pool.submit(self.fetch_rest_paginated, path, outfile)
                for path, outfile in all_tasks
            ]
            for f in as_completed(futures):
                f.result()

            # Follow-up deep inspection: fetch individual Rulesets and GHAS Configs by ID
            detail_futures = []
            for org in orgs:
                org_dir = self.out_dir / "orgs" / org

                # Expand individual Organization Rulesets
                rs_file = org_dir / "rulesets.json"
                if rs_file.exists():
                    try:
                        for rs in json.loads(rs_file.read_text(encoding="utf-8")):
                            if isinstance(rs, dict) and "id" in rs:
                                detail_futures.append(
                                    pool.submit(
                                        self.fetch_rest_paginated,
                                        f"/orgs/{org}/rulesets/{rs['id']}",
                                        org_dir / "rulesets" / f"ruleset-{rs['id']}.json",
                                    )
                                )
                    except Exception:
                        pass

                # Expand individual Code Security (GHAS) Configurations
                sec_file = org_dir / "code-security-configurations.json"
                if sec_file.exists():
                    try:
                        for cfg in json.loads(sec_file.read_text(encoding="utf-8")):
                            if isinstance(cfg, dict) and "id" in cfg:
                                detail_futures.append(
                                    pool.submit(
                                        self.fetch_rest_paginated,
                                        f"/orgs/{org}/code-security/configurations/{cfg['id']}",
                                        org_dir
                                        / "security-configs"
                                        / f"config-{cfg['id']}.json",
                                    )
                                )
                    except Exception:
                        pass

            for f in as_completed(detail_futures):
                f.result()

    # ==========================================================================
    # SECTION 6: MARKDOWN SUMMARY REPORT GENERATION (`AUDIT_SUMMARY.md`)
    # ==========================================================================

    @staticmethod
    def _load_json(path: Path) -> Any:
        """Safely loads a JSON file if it exists, returning None on missing/corrupt files."""
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def generate_markdown_report(self, enterprise: str, orgs: List[str]) -> Path:
        """
        Parses the collected Enterprise and Organization JSON files and generates
        a human-readable `AUDIT_SUMMARY.md` report with tables and access warnings.
        """
        ent_dir = self.out_dir / "enterprise"
        report_path = self.out_dir / "AUDIT_SUMMARY.md"

        # Load Enterprise-level evidence files
        gql = self._load_json(ent_dir / "01-policies-and-identity.json") or {}
        ent_data = (gql.get("data") or {}).get("enterprise") or {}
        owner_info = ent_data.get("ownerInfo") or {}
        billing = ent_data.get("billingInfo") or {}
        saml = owner_info.get("samlIdentityProvider") or {}

        ip_entries = self._load_json(ent_dir / "02-ip-allow-list.json") or []
        admins = self._load_json(ent_dir / "03-enterprise-admins.json") or []
        ent_actions = self._load_json(ent_dir / "actions-permissions.json") or {}
        ent_workflow = self._load_json(ent_dir / "actions-permissions-workflow.json") or {}
        ent_rulesets = self._load_json(ent_dir / "rulesets.json") or []
        ent_copilot = self._load_json(ent_dir / "copilot-billing.json") or {}

        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        lines: List[str] = [
            f"# GitHub Enterprise Cloud (GHEC) Audit Report: `{enterprise}`",
            "",
            f"- **Generated:** {now_str}",
            f"- **Enterprise Name:** {ent_data.get('name', enterprise)}",
            f"- **Enterprise URL:** {ent_data.get('url', f'https://github.com/enterprises/{enterprise}')}",
            f"- **Total Organizations Discovered:** {len(orgs)}",
            f"- **Licensed Users:** {billing.get('allLicensableUsersCount', 'N/A')}",
            "",
            "---",
            "",
            "## 1. Enterprise Security & Identity",
            "",
            "| Control | Setting / Value | Source File |",
            "| :--- | :--- | :--- |",
            f"| **Two-Factor Authentication (2FA)** | `{owner_info.get('twoFactorRequiredSetting', 'N/A')}` | `enterprise/01-policies-and-identity.json` |",
            f"| **SAML SSO Configured** | `{'Yes (' + saml.get('ssoUrl', '') + ')' if saml else 'No'}` | `enterprise/01-policies-and-identity.json` |",
            f"| **IP Allow List Enabled** | `{owner_info.get('ipAllowListEnabledSetting', 'N/A')}` ({len(ip_entries)} entries) | `enterprise/02-ip-allow-list.json` |",
            f"| **IP Allow List for Installed Apps** | `{owner_info.get('ipAllowListForInstalledAppsEnabledSetting', 'N/A')}` | `enterprise/01-policies-and-identity.json` |",
            f"| **Notification Delivery Restriction** | `{owner_info.get('notificationDeliveryRestrictionEnabledSetting', 'N/A')}` | `enterprise/01-policies-and-identity.json` |",
            f"| **Enterprise Owners / Billing Mgrs** | `{len(admins)}` account(s) | `enterprise/03-enterprise-admins.json` |",
            "",
            "## 2. Enterprise Member & Repository Policies",
            "",
            "| Policy | Value |",
            "| :--- | :--- |",
            f"| **Default Repository Permission** | `{owner_info.get('defaultRepositoryPermissionSetting', 'N/A')}` |",
            f"| **Members Can Create Repositories** | `{owner_info.get('membersCanCreateRepositoriesSetting', 'N/A')}` |",
            f"| **Create Public / Private / Internal** | Public: `{owner_info.get('membersCanCreatePublicRepositoriesSetting')}` / Private: `{owner_info.get('membersCanCreatePrivateRepositoriesSetting')}` / Internal: `{owner_info.get('membersCanCreateInternalRepositoriesSetting')}` |",
            f"| **Members Can Change Repo Visibility** | `{owner_info.get('membersCanChangeRepositoryVisibilitySetting', 'N/A')}` |",
            f"| **Members Can Delete Repositories** | `{owner_info.get('membersCanDeleteRepositoriesSetting', 'N/A')}` |",
            f"| **Members Can Invite Collaborators** | `{owner_info.get('membersCanInviteCollaboratorsSetting', 'N/A')}` |",
            f"| **Members Can Update Protected Branches** | `{owner_info.get('membersCanUpdateProtectedBranchesSetting', 'N/A')}` |",
            f"| **Actions Allowed Policy** | `{ent_actions.get('allowed_actions', 'N/A')}` (Enabled Orgs: `{ent_actions.get('enabled_organizations', 'N/A')}`) |",
            f"| **Default `GITHUB_TOKEN` Permissions** | `{ent_workflow.get('default_workflow_permissions', 'N/A')}` (Can approve PRs: `{ent_workflow.get('can_approve_pull_request_reviews', 'N/A')}`) |",
            f"| **Enterprise Rulesets** | `{len(ent_rulesets) if isinstance(ent_rulesets, list) else 0}` active ruleset(s) |",
            f"| **Copilot Seat Management** | `{ent_copilot.get('seat_management_setting', 'N/A')}` (Total seats: `{(ent_copilot.get('seat_breakdown') or {}).get('total', 'N/A')}`) |",
            "",
            "---",
            "",
            "## 3. Organization Settings Matrix",
            "",
            "| Organization | Access Status | 2FA Required | Base Repo Perm | Public Repo Creation | Secret Scanning / Push Prot. | Actions Policy | Default Token Perm | Rulesets | Apps | Webhooks |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        limited_orgs: List[str] = []

        # Build one summary row per Organization
        for org in orgs:
            org_dir = self.out_dir / "orgs" / org
            gen = self._load_json(org_dir / "01-general-settings.json")
            act = self._load_json(org_dir / "actions-permissions.json") or {}
            wf = self._load_json(org_dir / "actions-permissions-workflow.json") or {}
            rs = self._load_json(org_dir / "rulesets.json")
            apps = self._load_json(org_dir / "installations.json") or {}
            hooks = self._load_json(org_dir / "hooks.json")

            # In GHEC, `/orgs/{org}` only returns owner-level fields like
            # `two_factor_requirement_enabled` if the caller is an Organization Owner.
            if not isinstance(gen, dict) or "two_factor_requirement_enabled" not in gen:
                limited_orgs.append(org)
                access_badge = "⚠️ Limited (Not Org Owner)"
            else:
                access_badge = "✅ Full (Org Owner)"

            gen = gen if isinstance(gen, dict) else {}
            two_fa = gen.get("two_factor_requirement_enabled", "🔒 Hidden")
            base_perm = gen.get("default_repository_permission", "🔒 Hidden")
            pub_repo = gen.get("members_can_create_public_repositories", "🔒 Hidden")
            sec_scan = gen.get("secret_scanning_enabled_for_new_repositories", "N/A")
            push_prot = gen.get("secret_scanning_push_protection_enabled_for_new_repositories", "N/A")
            act_policy = act.get("allowed_actions", "🔒 Hidden")
            wf_perm = wf.get("default_workflow_permissions", "🔒 Hidden")
            rs_count = len(rs) if isinstance(rs, list) else "🔒"
            app_count = apps.get("total_count", "🔒") if isinstance(apps, dict) else "🔒"
            hook_count = len(hooks) if isinstance(hooks, list) else "🔒"

            lines.append(
                f"| **`{org}`** | {access_badge} | `{two_fa}` | `{base_perm}` | `{pub_repo}` | `{sec_scan}` / `{push_prot}` | `{act_policy}` | `{wf_perm}` | `{rs_count}` | `{app_count}` | `{hook_count}` |"
            )

        # Highlight any organizations where internal settings were hidden due to missing Org Owner role
        if limited_orgs:
            lines.extend(
                [
                    "",
                    "> [!WARNING]",
                    f"> **{len(limited_orgs)} organization(s) returned limited or forbidden (`403`/`404`) settings:** `{', '.join(limited_orgs)}`",
                    "> In GHEC, Enterprise Owners must also be an **Organization Owner** of each child organization to read internal org settings via the REST API.",
                    "> Fix: Go to **Enterprise Settings → Organizations**, click `...` next to those organizations, and select **Join as an owner**.",
                ]
            )
            print(
                f"\n[!] WARNING: {len(limited_orgs)} org(s) returned limited settings (not an Org Owner): {', '.join(limited_orgs)}"
            )

        lines.extend(
            [
                "",
                "---",
                "",
                "## 4. Evidence File Index",
                "",
                "- `enterprise/01-policies-and-identity.json` — GraphQL Enterprise policies, SAML, verified domains, SSH CAs",
                "- `enterprise/02-ip-allow-list.json` — All Enterprise IP Allow List CIDR entries",
                "- `enterprise/03-enterprise-admins.json` — All Enterprise Owners & Billing Managers",
                "- `enterprise/04-organizations-list.json` — Complete list of Enterprise Organizations",
                "- `enterprise/99-recent-config-audit-log.json` — Audit log stream of recent configuration changes",
                "- `orgs/<org>/01-general-settings.json` — Full Organization configuration payload",
                "- `orgs/<org>/rulesets/` — Individual JSON definitions for every branch/tag ruleset",
                "- `orgs/<org>/security-configs/` — Individual GHAS Code Security configuration payloads",
                "",
            ]
        )

        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path


# ==============================================================================
# SECTION 7: COMMAND-LINE INTERFACE (CLI) ENTRY POINT
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-Only GitHub Enterprise Cloud (GHEC) Settings Auditor"
    )
    parser.add_argument("enterprise", help="GHEC Enterprise slug (from github.com/enterprises/<slug>)")
    parser.add_argument("--token", help="GitHub Token (or uses GITHUB_TOKEN / gh auth token)")
    parser.add_argument(
        "--workers",
        type=int,
        default=16,
        help="Concurrent HTTP worker threads (default: 16)",
    )
    args = parser.parse_args()

    token = get_token(args.token)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = Path(f"ghec-audit-{args.enterprise}-{timestamp}")
    out_dir.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    auditor = ReadOnlyGitHubAuditor(token=token, out_dir=out_dir, workers=args.workers)
    orgs = auditor.audit_enterprise(args.enterprise)
    auditor.audit_organizations(orgs)
    report_path = auditor.generate_markdown_report(args.enterprise, orgs)
    elapsed = time.perf_counter() - start

    print(f"\nAudit Complete in {elapsed:.2f}s!")
    print(f" -> Raw JSON Evidence: {out_dir}/")
    print(f" -> Markdown Summary : {report_path}")


if __name__ == "__main__":
    main()
