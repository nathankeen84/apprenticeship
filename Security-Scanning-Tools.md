# Security Scanning Tools Integration

## Overview

The compliance pipeline integrates multiple enterprise-grade security scanning tools for comprehensive vulnerability detection and CIS benchmark compliance validation.

---

## Scanning Tools

### 1. AWS Inspector

**Purpose:** Automated vulnerability management and CIS compliance scanning for AWS resources

**Capabilities:**
- EC2 instance vulnerability scanning
- ECR container image scanning
- Network reachability analysis
- CIS benchmark compliance checks
- CVE detection and prioritization
- Integration with AWS Security Hub

**Scan Coverage:**
- Operating system vulnerabilities
- Application vulnerabilities
- Network exposure
- CIS benchmarks for Amazon Linux, Ubuntu, Windows
- Container vulnerabilities in ECR

**API Integration:**
```bash
# Enable Inspector
aws inspector2 enable --resource-types EC2 ECR

# Create findings report
aws inspector2 create-findings-report \
    --report-format JSON \
    --s3-destination bucketName=compliance-reports

# List findings
aws inspector2 list-findings \
    --filter-criteria '{"severities":[{"comparison":"EQUALS","value":"CRITICAL"}]}' \
    --max-results 1000
```

**Output Format:** JSON with CVE details, severity, affected resources

**Pricing:** Pay per scan (EC2 instances and container images)

---

### 2. Qualys

**Purpose:** Comprehensive vulnerability management and compliance scanning

**Capabilities:**
- Vulnerability scanning (on-premise and cloud)
- CIS benchmark compliance
- PCI DSS compliance
- Web application scanning
- Container security
- Asset inventory and discovery
- Patch management insights

**Scan Coverage:**
- Operating systems (Linux, Windows, Unix)
- Network devices
- Web applications
- Databases
- Cloud infrastructure (AWS, Azure, GCP)
- Containers and Kubernetes

**API Integration:**
```bash
# Launch vulnerability scan
curl -u "$QUALYS_USER:$QUALYS_PASS" \
    -H "X-Requested-With: curl" \
    "https://qualysapi.qualys.com/api/2.0/fo/scan/?action=launch&scan_title=Compliance-Scan&target_from=assets&option_title=CIS_Benchmark"

# Fetch scan results
curl -u "$QUALYS_USER:$QUALYS_PASS" \
    -H "X-Requested-With: curl" \
    "https://qualysapi.qualys.com/api/2.0/fo/scan/?action=fetch&scan_ref=scan/12345"
```

**Output Format:** XML/JSON with QID (Qualys ID), CVE, severity, remediation

**Pricing:** Subscription-based (per asset)

---

### 3. Tenable.io

**Purpose:** Vulnerability management and exposure management platform

**Capabilities:**
- Vulnerability scanning
- CIS benchmark compliance
- Configuration auditing
- Web application scanning
- Container security
- Cloud infrastructure scanning
- Exposure scoring (VPR - Vulnerability Priority Rating)

**Scan Coverage:**
- Operating systems
- Network devices
- Web applications
- Databases
- Cloud platforms (AWS, Azure, GCP)
- Containers and Kubernetes
- IoT devices

**API Integration:**
```bash
# Launch scan
curl -X POST \
    -H "X-ApiKeys: accessKey=$TENABLE_ACCESS_KEY; secretKey=$TENABLE_SECRET_KEY" \
    -H "Content-Type: application/json" \
    -d '{"uuid":"template-uuid","settings":{"name":"Compliance-Scan","text_targets":"10.0.0.0/24"}}' \
    https://cloud.tenable.com/scans

# Export scan results
curl -X POST \
    -H "X-ApiKeys: accessKey=$TENABLE_ACCESS_KEY; secretKey=$TENABLE_SECRET_KEY" \
    https://cloud.tenable.com/scans/{scan_id}/export?format=json
```

**Output Format:** JSON with CVE, VPR score, CVSS, remediation

**Pricing:** Subscription-based (per asset)

---

## Comparison Matrix

| Feature | AWS Inspector | Qualys | Tenable.io |
|---------|---------------|--------|------------|
| **Cloud Native** | AWS only | Multi-cloud | Multi-cloud |
| **On-Premise** | No | Yes | Yes |
| **CIS Benchmarks** | Yes | Yes | Yes |
| **Container Scanning** | ECR only | Yes | Yes |
| **Web App Scanning** | No | Yes | Yes |
| **API Access** | AWS CLI/SDK | REST API | REST API |
| **Pricing Model** | Pay per scan | Subscription | Subscription |
| **Deployment** | Agentless | Agent/Agentless | Agent/Agentless |
| **Real-time Monitoring** | Yes | Yes | Yes |
| **Compliance Frameworks** | CIS, PCI DSS | CIS, PCI DSS, HIPAA, SOC 2 | CIS, PCI DSS, HIPAA, SOC 2 |

---

## Integration in Pipeline

### Stage 2: CIS Benchmark Scans

The pipeline runs all three tools in parallel within the CIS Benchmarks stage:

```
CIS Benchmarks Stage (security-scanner agent)
├─ Docker CIS (Docker Bench Security)
├─ Kubernetes CIS (kube-bench)
├─ AWS CIS (Prowler)
├─ OS Hardening (OpenSCAP)
├─ AWS Inspector (automated scanning)
├─ Qualys (comprehensive scanning)
└─ Tenable (vulnerability management)
```

**Execution Time:** ~15-20 minutes (parallel execution)

---

## Credentials Required

### AWS Inspector
- AWS credentials with Inspector permissions
- IAM policy: `AmazonInspector2FullAccess` or custom policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "inspector2:*",
        "ec2:DescribeInstances",
        "ecr:DescribeImages"
      ],
      "Resource": "*"
    }
  ]
}
```

### Qualys
- Qualys username and password
- API URL (varies by region)
- Jenkins credential ID: `qualys-creds`

### Tenable.io
- Access key
- Secret key
- Jenkins credential IDs: `tenable-api-key`, `tenable-secret-key`

---

## Output Artifacts

### AWS Inspector
```
artifacts/cis/inspector/
├── assessment.json       # Assessment run details
└── findings.json         # Vulnerability findings
```

### Qualys
```
artifacts/cis/qualys/
├── scan-launch.xml       # Scan initiation response
└── scan-results.xml      # Vulnerability results
```

### Tenable
```
artifacts/cis/tenable/
├── scan-launch.json      # Scan creation response
└── scan-results.json     # Vulnerability findings
```

---

## Analysis Integration

All scan results are processed in Stage 3 (Analysis & Assessment):

1. **Normalization:** Convert different formats to common schema
2. **Deduplication:** Remove duplicate findings across tools
3. **Risk Scoring:** Assign unified risk scores
4. **Compliance Mapping:** Map to CIS benchmarks and other frameworks
5. **Prioritization:** Rank findings by severity and exploitability

---

## Benefits of Multi-Tool Approach

### Comprehensive Coverage
- **AWS Inspector:** Deep AWS integration, automated scanning
- **Qualys:** Broad platform support, mature vulnerability database
- **Tenable:** Advanced exposure management, VPR scoring

### Reduced False Positives
- Cross-validation between tools
- Higher confidence in findings confirmed by multiple scanners

### Compliance Assurance
- Multiple perspectives on CIS benchmark compliance
- Satisfies audit requirements for diverse scanning tools

### Risk Mitigation
- No single point of failure
- Different detection engines catch different vulnerabilities

---

## Best Practices

### Scan Scheduling
- **AWS Inspector:** Continuous scanning (always-on)
- **Qualys:** Daily scheduled scans
- **Tenable:** Daily scheduled scans

### Scan Targets
- Define consistent target lists across all tools
- Use asset tags for dynamic targeting
- Exclude development/test environments from production scans

### Result Processing
- Aggregate findings from all tools
- Deduplicate based on CVE/vulnerability ID
- Prioritize based on:
  - Severity (Critical > High > Medium > Low)
  - Exploitability (CVSS score, VPR)
  - Asset criticality
  - Exposure (internet-facing vs internal)

### Remediation Workflow
1. Critical findings → Immediate action (Jira ticket, SNS alert)
2. High findings → Fix within 7 days
3. Medium findings → Fix within 30 days
4. Low findings → Fix within 90 days

---

## Cost Optimization

### AWS Inspector
- Enable only for production accounts
- Use scheduled scanning vs continuous for cost savings
- Leverage free tier (first 90 days)

### Qualys
- Optimize asset count (remove decommissioned assets)
- Use agent-based scanning for better efficiency
- Leverage scan templates to reduce scan time

### Tenable
- Optimize asset count
- Use discovery scans to identify active assets
- Schedule scans during off-peak hours

---

## Troubleshooting

### AWS Inspector Issues
**Problem:** No findings returned
- Verify Inspector is enabled: `aws inspector2 get-configuration`
- Check IAM permissions
- Ensure EC2 instances have SSM agent installed

### Qualys Issues
**Problem:** Scan fails to launch
- Verify API credentials
- Check scan target accessibility
- Verify scan template exists

### Tenable Issues
**Problem:** API authentication fails
- Verify access and secret keys
- Check API rate limits
- Ensure correct API endpoint (cloud.tenable.com)

---

## Reporting

All three tools contribute to the unified compliance report:

### Executive Summary
- Total vulnerabilities by severity
- CIS benchmark compliance score
- Trend analysis (week-over-week, month-over-month)

### Technical Report
- Detailed findings from each tool
- CVE details with CVSS scores
- Affected assets
- Remediation recommendations

### Compliance Report
- CIS benchmark control mapping
- Pass/fail status per control
- Evidence of scanning (screenshots, logs)

---

## Future Enhancements

- **Automated Remediation:** Auto-patch based on scan findings
- **Machine Learning:** Predict vulnerability trends
- **Integration with SOAR:** Automated incident response
- **Custom Dashboards:** Real-time vulnerability metrics
- **Threat Intelligence:** Correlate findings with threat feeds

---

**Document Version:** 1.0  
**Last Updated:** November 20, 2025
