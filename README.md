# Compliance Pipeline with Test Pyramid Integration

A comprehensive Jenkins-based compliance pipeline that integrates CIS benchmarks, GDPR controls, audit trails, and the complete test pyramid for enterprise-grade security and quality assurance.

## Overview

This pipeline provides automated compliance validation and testing across multiple dimensions:

- **CIS Benchmarks:** OS, container, Kubernetes, and cloud infrastructure hardening
- **GDPR Controls:** Data mapping, encryption, access controls, consent management
- **Audit Trails:** Immutable logging with 7+ year retention
- **Test Pyramid:** Unit, integration, contract, component, and E2E tests
- **Security Testing:** SAST, DAST, dependency scanning, secret detection
- **Performance Testing:** Load, stress, and endurance testing

## Architecture

The pipeline executes across multiple Jenkins agents in parallel for optimal performance:

```
Collection → Parallel Scanning & Testing → Analysis → Reporting → Archival
   (1 agent)      (10+ agents)            (1 agent)  (2 agents)  (1 agent)
```

### Execution Time
- **Sequential:** ~90 minutes
- **Parallel:** ~45 minutes (50% reduction)

## Files

- **Jenkinsfile** - Complete Jenkins pipeline with parallel agent execution
- **compliance-pipeline.md** - Detailed documentation of compliance components
- **compliance-pipeline-diagram.txt** - Visual ASCII diagram of the pipeline
- **jenkins-pipeline-diagram.txt** - Jenkins-specific agent allocation diagram
- **test-pyramid-integration.md** - Comprehensive test pyramid documentation
- **implementation-example.yaml** - GitHub Actions example (for reference)

## Jenkins Agent Requirements

### Required Agent Labels

| Agent Label | Purpose | Resources |
|-------------|---------|-----------|
| `compliance-collector` | Data collection and archival | 2 CPU, 4GB RAM |
| `security-scanner` | CIS and security scans | 4 CPU, 8GB RAM |
| `compliance-gdpr` | GDPR validation | 2 CPU, 4GB RAM |
| `audit-collector` | Audit trail collection | 2 CPU, 4GB RAM |
| `test-unit` | Unit tests | 2 CPU, 4GB RAM |
| `test-integration` | Integration tests | 4 CPU, 8GB RAM |
| `test-contract` | Contract tests | 2 CPU, 4GB RAM |
| `test-component` | Component tests | 4 CPU, 8GB RAM |
| `test-e2e` | E2E tests | 4 CPU, 8GB RAM |
| `test-performance` | Performance tests | 8 CPU, 16GB RAM |
| `compliance-analyzer` | Analysis and scoring | 4 CPU, 8GB RAM |
| `report-generator` | Report generation | 2 CPU, 4GB RAM |
| `remediation-agent` | Auto-remediation | 2 CPU, 4GB RAM |

## Prerequisites

### Tools Required

#### Security Scanning
- Docker
- kubectl
- OpenSCAP
- AWS CLI (with Inspector access)
- Prowler
- kube-bench
- Trivy
- Semgrep
- OWASP ZAP
- Gitleaks
- TruffleHog
- Qualys API access
- Tenable.io API access

#### Testing
- pytest (Python)
- npm/node (JavaScript)
- Cypress or Playwright
- JMeter
- K6
- Testcontainers

#### Reporting
- Python 3.8+
- Required Python packages (see requirements.txt)

### Jenkins Plugins
- Pipeline
- Docker Pipeline
- Kubernetes
- JUnit
- HTML Publisher
- AWS SNS Plugin (or use AWS CLI)
- Credentials Binding
- Stash/Unstash

### Credentials Required

Configure these in Jenkins credentials:
- `db-url` - Database connection string
- `elk-creds` - ELK Stack username/password
- `dashboard-token` - Dashboard API token
- `jira-creds` - Jira username/password
- `qualys-creds` - Qualys username/password
- `tenable-api-key` - Tenable access key
- `tenable-secret-key` - Tenable secret key
- AWS credentials (for CloudTrail, S3, Inspector)

## Configuration

### Environment Variables

Set these in Jenkins or the Jenkinsfile:

```groovy
COMPLIANCE_THRESHOLD = '85'        // Minimum compliance score
CRITICAL_FINDINGS_MAX = '0'        // Maximum critical findings
ELASTICSEARCH_URL = 'https://elasticsearch.example.com'
KIBANA_URL = 'https://kibana.example.com'
DASHBOARD_URL = 'https://dashboard.example.com'
JIRA_URL = 'https://jira.example.com'
SONAR_URL = 'https://sonar.example.com'
TARGET_URL = 'https://app.example.com'  // For DAST
```

### Pipeline Parameters

The pipeline supports these parameters:

- `AUTO_REMEDIATE` (boolean) - Enable automatic remediation
- `SKIP_E2E` (boolean) - Skip E2E tests for faster execution
- `SCAN_SCOPE` (choice) - Full, Quick, or Custom scan

## Usage

### Trigger Pipeline

#### Scheduled (Recommended)
```groovy
// Daily at 2 AM
triggers {
    cron('0 2 * * *')
}
```

#### Manual
1. Navigate to Jenkins job
2. Click "Build with Parameters"
3. Configure options
4. Click "Build"

#### On Commit
```groovy
triggers {
    pollSCM('H/5 * * * *')  // Poll every 5 minutes
}
```

### View Results

#### Jenkins UI
- **Test Results:** JUnit plugin displays all test results
- **Coverage:** HTML Publisher shows coverage reports
- **Artifacts:** Download compliance reports and evidence packages

#### Dashboards
- Real-time compliance score
- Test pyramid metrics
- Trend analysis
- Risk heatmaps

#### Notifications
- AWS SNS: Published to compliance topic
- Email: Via SNS email subscriptions
- Jira: Auto-created tickets for failures

## Test Pyramid Distribution

```
E2E Tests:         5%  (~50 tests)   - Critical user journeys
Component Tests:   10% (~100 tests)  - Service-level validation
Contract Tests:    15% (~150 tests)  - API contracts
Integration Tests: 20% (~200 tests)  - Module interactions
Unit Tests:        50% (~500 tests)  - Function-level validation
```

## Compliance Frameworks

The pipeline validates against:

- **CIS Benchmarks v8**
  - Operating Systems (Linux, Windows)
  - Docker
  - Kubernetes
  - AWS, Azure, GCP

- **GDPR**
  - Article 5 (Data principles)
  - Article 25 (Privacy by design)
  - Article 30 (Records of processing)
  - Article 32 (Security of processing)

- **ISO 27001**
- **SOC 2**
- **NIST Cybersecurity Framework**

## Outputs

### Reports Generated

1. **Executive Summary** (PDF)
   - Compliance score
   - Critical findings
   - Trend analysis
   - Recommendations

2. **Technical Findings** (PDF)
   - Detailed vulnerability list
   - Risk scores
   - Remediation steps
   - Code references

3. **Test Pyramid Report** (HTML)
   - Test distribution
   - Coverage metrics
   - Pass/fail rates
   - Execution times

4. **Audit Evidence Package** (ZIP)
   - All scan results
   - Test outputs
   - Logs and screenshots
   - Compliance mappings

### Artifacts Archived

All artifacts are stored in:
- Jenkins (30 days)
- S3 Glacier (7+ years for compliance)

## Remediation

### Automatic Remediation

When `AUTO_REMEDIATE=true`, the pipeline automatically fixes:

- Security group misconfigurations
- Missing encryption
- Outdated dependencies
- Configuration drift
- Policy violations

### Manual Remediation

For issues requiring human review:
1. Jira ticket created automatically
2. Assigned to security team
3. Tracked until resolution
4. Re-scan triggered on fix

## Monitoring

### Key Metrics

- **Compliance Score:** Overall compliance percentage
- **Critical Findings:** Count of critical issues
- **MTTR:** Mean time to remediate
- **Test Coverage:** Code coverage percentage
- **Audit Coverage:** Percentage of events captured
- **Pipeline Success Rate:** Build success percentage

### Alerts

Alerts are sent for:
- Compliance score below threshold
- Critical findings detected
- Pipeline failures
- Test failures above threshold
- Performance degradation

## Troubleshooting

### Common Issues

#### Pipeline Timeout
- Increase timeout in pipeline options
- Skip E2E tests for faster execution
- Check agent availability

#### Agent Unavailable
- Verify agent labels are correct
- Check agent connectivity
- Review agent resource usage

#### Test Failures
- Check test logs in Jenkins
- Review screenshots/videos for E2E tests
- Verify test environment is healthy

#### Scan Failures
- Verify tool installations
- Check credentials are valid
- Review network connectivity

### Debug Mode

Enable debug logging:
```groovy
environment {
    DEBUG = 'true'
    LOG_LEVEL = 'DEBUG'
}
```

## Best Practices

1. **Run Daily:** Schedule pipeline to run daily at minimum
2. **Review Weekly:** Review compliance trends weekly
3. **Fix Critical First:** Prioritize critical findings
4. **Update Benchmarks:** Keep CIS benchmarks current
5. **Maintain Tests:** Keep test pyramid balanced
6. **Archive Evidence:** Ensure 7+ year retention
7. **Monitor Trends:** Track compliance over time
8. **Automate Remediation:** Auto-fix where safe

## Contributing

### Adding New Scans

1. Create new stage in Jenkinsfile
2. Add agent label
3. Implement scan logic
4. Stash results
5. Update analysis stage to consume results

### Adding New Tests

1. Create test files in appropriate directory
2. Update test execution commands
3. Ensure JUnit XML output
4. Add to test metrics calculation

## License

[Your License Here]

## Support

For issues or questions:
- Create Jira ticket in SEC project
- Contact: security-team@example.com
- SNS Topic: arn:aws:sns:region:account:compliance-pipeline

## References

- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [GDPR Official Text](https://gdpr-info.eu/)
- [Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)
- [Jenkins Pipeline Documentation](https://www.jenkins.io/doc/book/pipeline/)
