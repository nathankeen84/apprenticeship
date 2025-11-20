// Compliance Pipeline with Test Pyramid Integration
// Parallel execution across multiple agents

pipeline {
    agent none
    
    options {
        buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '30'))
        timestamps()
        timeout(time: 2, unit: 'HOURS')
        disableConcurrentBuilds()
    }
    
    environment {
        COMPLIANCE_THRESHOLD = '85'
        CRITICAL_FINDINGS_MAX = '0'
        SCAN_DATE = sh(script: "date +%Y%m%d-%H%M%S", returnStdout: true).trim()
    }
    
    stages {
        // ====================================================================
        // STAGE 1: COLLECTION (Single Agent)
        // ====================================================================
        stage('Data Collection') {
            agent { label 'compliance-collector' }
            steps {
                script {
                    echo "🔍 Collecting compliance data..."
                    sh '''
                        mkdir -p artifacts/collection
                        find . -name "*.tf" -o -name "*.yaml" -o -name "*.json" > artifacts/collection/configs.txt
                        echo "Data collection complete"
                    '''
                }
            }
            post {
                success {
                    stash name: 'collection-data', includes: 'artifacts/collection/**'
                }
            }
        }
        
        // ====================================================================
        // STAGE 2: PARALLEL SCANNING & TESTING
        // ====================================================================
        stage('Parallel Scanning & Testing') {
            parallel {
                // ============================================================
                // CIS BENCHMARK SCANS
                // ============================================================
                stage('CIS Benchmarks') {
                    agent { label 'security-scanner' }
                    stages {
                        stage('Docker CIS') {
                            steps {
                                script {
                                    echo "🐳 Running Docker CIS Benchmark..."
                                    sh '''
                                        mkdir -p artifacts/cis/docker
                                        docker run --rm --net host --pid host \
                                            --userns host --cap-add audit_control \
                                            -v /var/lib:/var/lib \
                                            -v /var/run/docker.sock:/var/run/docker.sock \
                                            docker/docker-bench-security \
                                            > artifacts/cis/docker/results.txt || true
                                    '''
                                }
                            }
                        }
                        
                        stage('AWS Inspector') {
                            steps {
                                script {
                                    echo "🔍 Running AWS Inspector Scans..."
                                    sh '''
                                        mkdir -p artifacts/cis/inspector
                                        # Start Inspector assessment run
                                        aws inspector2 create-findings-report \
                                            --report-format JSON \
                                            --s3-destination bucketName=compliance-reports,keyPrefix=inspector/ \
                                            > artifacts/cis/inspector/assessment.json || true
                                        
                                        # Get findings
                                        aws inspector2 list-findings \
                                            --filter-criteria '{"severities":[{"comparison":"EQUALS","value":"CRITICAL"},{"comparison":"EQUALS","value":"HIGH"}]}' \
                                            --max-results 1000 \
                                            > artifacts/cis/inspector/findings.json || true
                                    '''
                                }
                            }
                        }
                        
                        stage('Qualys Scan') {
                            steps {
                                script {
                                    echo "🛡️ Running Qualys Vulnerability Scan..."
                                    withCredentials([usernamePassword(credentialsId: 'qualys-creds', usernameVariable: 'QUALYS_USER', passwordVariable: 'QUALYS_PASS')]) {
                                        sh '''
                                            mkdir -p artifacts/cis/qualys
                                            # Launch Qualys scan
                                            curl -u "$QUALYS_USER:$QUALYS_PASS" \
                                                -H "X-Requested-With: curl" \
                                                "https://qualysapi.qualys.com/api/2.0/fo/scan/?action=launch&scan_title=Compliance-Scan-${BUILD_NUMBER}&target_from=assets&option_title=CIS_Benchmark" \
                                                > artifacts/cis/qualys/scan-launch.xml || true
                                            
                                            # Wait and fetch results
                                            sleep 300
                                            curl -u "$QUALYS_USER:$QUALYS_PASS" \
                                                -H "X-Requested-With: curl" \
                                                "https://qualysapi.qualys.com/api/2.0/fo/scan/?action=list&scan_ref=Compliance-Scan-${BUILD_NUMBER}" \
                                                > artifacts/cis/qualys/scan-results.xml || true
                                        '''
                                    }
                                }
                            }
                        }
                        
                        stage('Tenable Scan') {
                            steps {
                                script {
                                    echo "🔐 Running Tenable.io Scan..."
                                    withCredentials([string(credentialsId: 'tenable-api-key', variable: 'TENABLE_ACCESS_KEY'), 
                                                   string(credentialsId: 'tenable-secret-key', variable: 'TENABLE_SECRET_KEY')]) {
                                        sh '''
                                            mkdir -p artifacts/cis/tenable
                                            # Launch Tenable scan
                                            curl -X POST \
                                                -H "X-ApiKeys: accessKey=$TENABLE_ACCESS_KEY; secretKey=$TENABLE_SECRET_KEY" \
                                                -H "Content-Type: application/json" \
                                                -d '{"uuid":"template-uuid","settings":{"name":"Compliance-Scan-'${BUILD_NUMBER}'","enabled":true,"text_targets":"'${SCAN_TARGETS}'"}}' \
                                                https://cloud.tenable.com/scans \
                                                > artifacts/cis/tenable/scan-launch.json || true
                                            
                                            # Export scan results
                                            SCAN_ID=$(cat artifacts/cis/tenable/scan-launch.json | jq -r '.scan.id')
                                            sleep 300
                                            curl -X POST \
                                                -H "X-ApiKeys: accessKey=$TENABLE_ACCESS_KEY; secretKey=$TENABLE_SECRET_KEY" \
                                                https://cloud.tenable.com/scans/$SCAN_ID/export?format=json \
                                                > artifacts/cis/tenable/scan-results.json || true
                                        '''
                                    }
                                }
                            }
                        }
                        
                        stage('Kubernetes CIS') {
                            steps {
                                script {
                                    echo "☸️  Running Kubernetes CIS Benchmark..."
                                    sh '''
                                        mkdir -p artifacts/cis/k8s
                                        kubectl apply -f https://raw.githubusercontent.com/aquasecurity/kube-bench/main/job.yaml
                                        sleep 30
                                        kubectl wait --for=condition=complete --timeout=300s job/kube-bench
                                        kubectl logs job/kube-bench > artifacts/cis/k8s/kube-bench.txt
                                        kubectl delete job kube-bench
                                    '''
                                }
                            }
                        }
                        
                        stage('Cloud CIS - AWS') {
                            steps {
                                script {
                                    echo "☁️  Running AWS Prowler CIS Benchmark..."
                                    sh '''
                                        mkdir -p artifacts/cis/aws
                                        docker run --rm \
                                            -v ~/.aws:/root/.aws:ro \
                                            toniblyx/prowler:latest \
                                            -M json-asff -f us-east-1 \
                                            > artifacts/cis/aws/prowler-results.json || true
                                    '''
                                }
                            }
                        }
                        
                        stage('OS Hardening') {
                            steps {
                                script {
                                    echo "🖥️  Running OS Hardening Checks..."
                                    sh '''
                                        mkdir -p artifacts/cis/os
                                        # OpenSCAP scan
                                        oscap xccdf eval \
                                            --profile xccdf_org.ssgproject.content_profile_cis \
                                            --results artifacts/cis/os/results.xml \
                                            /usr/share/xml/scap/ssg/content/ssg-ubuntu2004-ds.xml || true
                                    '''
                                }
                            }
                        }
                    }
                    post {
                        always {
                            stash name: 'cis-results', includes: 'artifacts/cis/**'
                            archiveArtifacts artifacts: 'artifacts/cis/**', allowEmptyArchive: true
                        }
                    }
                }
                
                // ============================================================
                // GDPR COMPLIANCE CHECKS
                // ============================================================
                stage('GDPR Compliance') {
                    agent { label 'compliance-gdpr' }
                    stages {
                        stage('Data Discovery') {
                            steps {
                                script {
                                    echo "🔎 Scanning for PII/Sensitive Data..."
                                    sh '''
                                        mkdir -p artifacts/gdpr
                                        python3 scripts/pii-scanner.py \
                                            --scan-path . \
                                            --output artifacts/gdpr/data-map.json
                                    '''
                                }
                            }
                        }
                        
                        stage('Encryption Validation') {
                            steps {
                                script {
                                    echo "🔐 Validating Encryption Controls..."
                                    sh '''
                                        python3 scripts/check-encryption.py \
                                            --at-rest --in-transit \
                                            --output artifacts/gdpr/encryption-report.json
                                    '''
                                }
                            }
                        }
                        
                        stage('Access Control Audit') {
                            steps {
                                script {
                                    echo "🔑 Auditing Access Controls..."
                                    sh '''
                                        python3 scripts/access-audit.py \
                                            --check-mfa --check-least-privilege \
                                            --output artifacts/gdpr/access-report.json
                                    '''
                                }
                            }
                        }
                        
                        stage('Data Retention Check') {
                            steps {
                                script {
                                    echo "📅 Validating Data Retention Policies..."
                                    sh '''
                                        python3 scripts/retention-check.py \
                                            --policy-file policies/retention.yaml \
                                            --output artifacts/gdpr/retention-report.json
                                    '''
                                }
                            }
                        }
                        
                        stage('Consent Management') {
                            steps {
                                script {
                                    echo "✅ Checking Consent Records..."
                                    withCredentials([string(credentialsId: 'db-url', variable: 'DB_URL')]) {
                                        sh '''
                                            python3 scripts/consent-audit.py \
                                                --database-url $DB_URL \
                                                --output artifacts/gdpr/consent-report.json
                                        '''
                                    }
                                }
                            }
                        }
                    }
                    post {
                        always {
                            stash name: 'gdpr-results', includes: 'artifacts/gdpr/**'
                            archiveArtifacts artifacts: 'artifacts/gdpr/**', allowEmptyArchive: true
                        }
                    }
                }
                
                // ============================================================
                // AUDIT TRAIL COLLECTION
                // ============================================================
                stage('Audit Trails') {
                    agent { label 'audit-collector' }
                    stages {
                        stage('Authentication Events') {
                            steps {
                                script {
                                    echo "🔐 Collecting Authentication Events..."
                                    withCredentials([usernamePassword(credentialsId: 'elk-creds', usernameVariable: 'ELK_USER', passwordVariable: 'ELK_PASS')]) {
                                        sh '''
                                            mkdir -p artifacts/audit
                                            curl -X GET "$ELASTICSEARCH_URL/auth-logs-*/_search" \
                                                -u "$ELK_USER:$ELK_PASS" \
                                                -H "Content-Type: application/json" \
                                                -d '{"query":{"range":{"@timestamp":{"gte":"now-24h"}}},"size":10000}' \
                                                > artifacts/audit/auth-events.json
                                        '''
                                    }
                                }
                            }
                        }
                        
                        stage('API Activity') {
                            steps {
                                script {
                                    echo "📡 Collecting API Activity Logs..."
                                    sh '''
                                        aws cloudtrail lookup-events \
                                            --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
                                            --output json \
                                            > artifacts/audit/api-activity.json
                                    '''
                                }
                            }
                        }
                        
                        stage('Config Changes') {
                            steps {
                                script {
                                    echo "⚙️  Collecting Configuration Changes..."
                                    sh '''
                                        aws configservice describe-compliance-by-config-rule \
                                            --output json \
                                            > artifacts/audit/config-changes.json
                                    '''
                                }
                            }
                        }
                        
                        stage('Audit Integrity') {
                            steps {
                                script {
                                    echo "🔍 Validating Audit Log Integrity..."
                                    sh '''
                                        python3 scripts/verify-audit-integrity.py \
                                            --logs artifacts/audit/ \
                                            --output artifacts/audit/integrity-report.json
                                    '''
                                }
                            }
                        }
                    }
                    post {
                        always {
                            stash name: 'audit-results', includes: 'artifacts/audit/**'
                            archiveArtifacts artifacts: 'artifacts/audit/**', allowEmptyArchive: true
                        }
                    }
                }
                
                // ============================================================
                // TEST PYRAMID - UNIT TESTS
                // ============================================================
                stage('Unit Tests') {
                    agent { label 'test-unit' }
                    steps {
                        script {
                            echo "🧪 Running Unit Tests (Test Pyramid - Base Layer)..."
                            sh '''
                                mkdir -p artifacts/tests/unit
                                # Run unit tests with coverage
                                pytest tests/unit/ \
                                    --cov=src \
                                    --cov-report=xml:artifacts/tests/unit/coverage.xml \
                                    --cov-report=html:artifacts/tests/unit/coverage-html \
                                    --junitxml=artifacts/tests/unit/junit.xml \
                                    -v
                            '''
                        }
                    }
                    post {
                        always {
                            junit 'artifacts/tests/unit/junit.xml'
                            publishHTML([
                                reportDir: 'artifacts/tests/unit/coverage-html',
                                reportFiles: 'index.html',
                                reportName: 'Unit Test Coverage'
                            ])
                            stash name: 'unit-test-results', includes: 'artifacts/tests/unit/**'
                        }
                    }
                }
                
                // ============================================================
                // TEST PYRAMID - INTEGRATION TESTS
                // ============================================================
                stage('Integration Tests') {
                    agent { label 'test-integration' }
                    steps {
                        script {
                            echo "🔗 Running Integration Tests (Test Pyramid - Middle Layer)..."
                            sh '''
                                mkdir -p artifacts/tests/integration
                                # Start dependencies
                                docker-compose -f docker-compose.test.yml up -d
                                sleep 10
                                
                                # Run integration tests
                                pytest tests/integration/ \
                                    --junitxml=artifacts/tests/integration/junit.xml \
                                    -v
                                
                                # Cleanup
                                docker-compose -f docker-compose.test.yml down
                            '''
                        }
                    }
                    post {
                        always {
                            junit 'artifacts/tests/integration/junit.xml'
                            stash name: 'integration-test-results', includes: 'artifacts/tests/integration/**'
                        }
                    }
                }
                
                // ============================================================
                // TEST PYRAMID - CONTRACT TESTS
                // ============================================================
                stage('Contract Tests') {
                    agent { label 'test-contract' }
                    steps {
                        script {
                            echo "📝 Running Contract Tests (Test Pyramid - API Layer)..."
                            sh '''
                                mkdir -p artifacts/tests/contract
                                # Run Pact contract tests
                                npm run test:contract -- \
                                    --reporter json \
                                    --reporter-options output=artifacts/tests/contract/results.json
                            '''
                        }
                    }
                    post {
                        always {
                            stash name: 'contract-test-results', includes: 'artifacts/tests/contract/**'
                        }
                    }
                }
                
                // ============================================================
                // TEST PYRAMID - COMPONENT TESTS
                // ============================================================
                stage('Component Tests') {
                    agent { label 'test-component' }
                    steps {
                        script {
                            echo "🧩 Running Component Tests (Test Pyramid - Service Layer)..."
                            sh '''
                                mkdir -p artifacts/tests/component
                                # Run component tests with test containers
                                pytest tests/component/ \
                                    --junitxml=artifacts/tests/component/junit.xml \
                                    -v
                            '''
                        }
                    }
                    post {
                        always {
                            junit 'artifacts/tests/component/junit.xml'
                            stash name: 'component-test-results', includes: 'artifacts/tests/component/**'
                        }
                    }
                }
                
                // ============================================================
                // TEST PYRAMID - E2E TESTS
                // ============================================================
                stage('E2E Tests') {
                    agent { label 'test-e2e' }
                    steps {
                        script {
                            echo "🎯 Running E2E Tests (Test Pyramid - Top Layer)..."
                            sh '''
                                mkdir -p artifacts/tests/e2e
                                # Run Cypress/Playwright E2E tests
                                npm run test:e2e -- \
                                    --reporter junit \
                                    --reporter-options mochaFile=artifacts/tests/e2e/junit.xml
                            '''
                        }
                    }
                    post {
                        always {
                            junit 'artifacts/tests/e2e/junit.xml'
                            archiveArtifacts artifacts: 'artifacts/tests/e2e/screenshots/**', allowEmptyArchive: true
                            archiveArtifacts artifacts: 'artifacts/tests/e2e/videos/**', allowEmptyArchive: true
                            stash name: 'e2e-test-results', includes: 'artifacts/tests/e2e/**'
                        }
                    }
                }
                
                // ============================================================
                // SECURITY TESTS
                // ============================================================
                stage('Security Tests') {
                    agent { label 'security-scanner' }
                    stages {
                        stage('SAST') {
                            steps {
                                script {
                                    echo "🔒 Running SAST (Static Application Security Testing)..."
                                    sh '''
                                        mkdir -p artifacts/security/sast
                                        # SonarQube scan
                                        sonar-scanner \
                                            -Dsonar.projectKey=compliance-pipeline \
                                            -Dsonar.sources=. \
                                            -Dsonar.host.url=$SONAR_URL \
                                            -Dsonar.login=$SONAR_TOKEN
                                        
                                        # Semgrep scan
                                        semgrep --config=auto --json \
                                            > artifacts/security/sast/semgrep-results.json
                                    '''
                                }
                            }
                        }
                        
                        stage('DAST') {
                            steps {
                                script {
                                    echo "🌐 Running DAST (Dynamic Application Security Testing)..."
                                    sh '''
                                        mkdir -p artifacts/security/dast
                                        # OWASP ZAP scan
                                        docker run --rm \
                                            -v $(pwd)/artifacts/security/dast:/zap/wrk/:rw \
                                            owasp/zap2docker-stable zap-baseline.py \
                                            -t $TARGET_URL \
                                            -J zap-report.json \
                                            -r zap-report.html || true
                                    '''
                                }
                            }
                        }
                        
                        stage('Dependency Scan') {
                            steps {
                                script {
                                    echo "📦 Running Dependency Vulnerability Scan..."
                                    sh '''
                                        mkdir -p artifacts/security/dependencies
                                        # OWASP Dependency Check
                                        dependency-check.sh \
                                            --project "Compliance Pipeline" \
                                            --scan . \
                                            --format JSON \
                                            --out artifacts/security/dependencies
                                        
                                        # Trivy scan
                                        trivy fs --format json \
                                            --output artifacts/security/dependencies/trivy-results.json .
                                    '''
                                }
                            }
                        }
                        
                        stage('Secret Scan') {
                            steps {
                                script {
                                    echo "🔑 Scanning for Secrets..."
                                    sh '''
                                        mkdir -p artifacts/security/secrets
                                        # Gitleaks scan
                                        gitleaks detect --source . \
                                            --report-format json \
                                            --report-path artifacts/security/secrets/gitleaks-report.json || true
                                        
                                        # TruffleHog scan
                                        trufflehog filesystem . \
                                            --json > artifacts/security/secrets/trufflehog-report.json || true
                                    '''
                                }
                            }
                        }
                    }
                    post {
                        always {
                            stash name: 'security-test-results', includes: 'artifacts/security/**'
                            archiveArtifacts artifacts: 'artifacts/security/**', allowEmptyArchive: true
                        }
                    }
                }
                
                // ============================================================
                // PERFORMANCE TESTS
                // ============================================================
                stage('Performance Tests') {
                    agent { label 'test-performance' }
                    steps {
                        script {
                            echo "⚡ Running Performance Tests..."
                            sh '''
                                mkdir -p artifacts/tests/performance
                                # JMeter load test
                                jmeter -n -t tests/performance/load-test.jmx \
                                    -l artifacts/tests/performance/results.jtl \
                                    -e -o artifacts/tests/performance/report
                                
                                # K6 performance test
                                k6 run --out json=artifacts/tests/performance/k6-results.json \
                                    tests/performance/stress-test.js
                            '''
                        }
                    }
                    post {
                        always {
                            publishHTML([
                                reportDir: 'artifacts/tests/performance/report',
                                reportFiles: 'index.html',
                                reportName: 'Performance Test Report'
                            ])
                            stash name: 'performance-test-results', includes: 'artifacts/tests/performance/**'
                        }
                    }
                }
            }
        }
        
        // ====================================================================
        // STAGE 3: ANALYSIS & ASSESSMENT
        // ====================================================================
        stage('Analysis & Assessment') {
            agent { label 'compliance-analyzer' }
            steps {
                script {
                    echo "📊 Analyzing compliance and test results..."
                    
                    // Unstash all results
                    unstash 'cis-results'
                    unstash 'gdpr-results'
                    unstash 'audit-results'
                    unstash 'unit-test-results'
                    unstash 'integration-test-results'
                    unstash 'contract-test-results'
                    unstash 'component-test-results'
                    unstash 'e2e-test-results'
                    unstash 'security-test-results'
                    unstash 'performance-test-results'
                    
                    sh '''
                        mkdir -p artifacts/analysis
                        
                        # Risk scoring
                        python3 scripts/risk-scoring.py \
                            --cis-results artifacts/cis/ \
                            --gdpr-results artifacts/gdpr/ \
                            --audit-results artifacts/audit/ \
                            --security-results artifacts/security/ \
                            --output artifacts/analysis/risk-scores.json
                        
                        # Compliance mapping
                        python3 scripts/compliance-mapper.py \
                            --frameworks CIS,GDPR,ISO27001,SOC2,NIST \
                            --findings artifacts/analysis/risk-scores.json \
                            --output artifacts/analysis/compliance-map.json
                        
                        # Gap analysis
                        python3 scripts/gap-analysis.py \
                            --current artifacts/analysis/compliance-map.json \
                            --target policies/target-compliance.yaml \
                            --output artifacts/analysis/gaps.json
                        
                        # Test pyramid metrics
                        python3 scripts/test-metrics.py \
                            --test-results artifacts/tests/ \
                            --output artifacts/analysis/test-metrics.json
                        
                        # Calculate compliance score
                        python3 scripts/calculate-score.py \
                            --input artifacts/analysis/compliance-map.json \
                            --output artifacts/analysis/compliance-score.json
                    '''
                    
                    // Read compliance score
                    def scoreData = readJSON file: 'artifacts/analysis/compliance-score.json'
                    def complianceScore = scoreData.score
                    def criticalFindings = scoreData.critical_findings
                    
                    echo "Compliance Score: ${complianceScore}%"
                    echo "Critical Findings: ${criticalFindings}"
                    
                    // Check thresholds
                    if (complianceScore < COMPLIANCE_THRESHOLD.toInteger()) {
                        error "❌ Compliance score ${complianceScore}% is below threshold ${COMPLIANCE_THRESHOLD}%"
                    }
                    
                    if (criticalFindings > CRITICAL_FINDINGS_MAX.toInteger()) {
                        error "❌ Critical findings ${criticalFindings} exceed maximum ${CRITICAL_FINDINGS_MAX}"
                    }
                }
            }
            post {
                always {
                    stash name: 'analysis-results', includes: 'artifacts/analysis/**'
                    archiveArtifacts artifacts: 'artifacts/analysis/**'
                }
            }
        }
        
        // ====================================================================
        // STAGE 4: REPORTING & REMEDIATION
        // ====================================================================
        stage('Reporting & Remediation') {
            parallel {
                stage('Generate Reports') {
                    agent { label 'report-generator' }
                    steps {
                        script {
                            echo "📄 Generating compliance reports..."
                            unstash 'analysis-results'
                            
                            sh '''
                                mkdir -p artifacts/reports
                                
                                # Executive summary
                                python3 scripts/generate-report.py \
                                    --type executive \
                                    --input artifacts/analysis/compliance-map.json \
                                    --test-metrics artifacts/analysis/test-metrics.json \
                                    --output artifacts/reports/executive-summary.pdf
                                
                                # Technical findings report
                                python3 scripts/generate-report.py \
                                    --type technical \
                                    --input artifacts/analysis/risk-scores.json \
                                    --output artifacts/reports/technical-findings.pdf
                                
                                # Audit evidence package
                                python3 scripts/package-evidence.py \
                                    --all-artifacts artifacts/ \
                                    --output artifacts/reports/audit-evidence-${SCAN_DATE}.zip
                                
                                # Test pyramid report
                                python3 scripts/generate-test-report.py \
                                    --metrics artifacts/analysis/test-metrics.json \
                                    --output artifacts/reports/test-pyramid-report.html
                            '''
                            
                            // Publish to dashboard
                            withCredentials([string(credentialsId: 'dashboard-token', variable: 'API_TOKEN')]) {
                                sh '''
                                    curl -X POST "$DASHBOARD_URL/api/reports" \
                                        -H "Authorization: Bearer $API_TOKEN" \
                                        -F "executive=@artifacts/reports/executive-summary.pdf" \
                                        -F "technical=@artifacts/reports/technical-findings.pdf" \
                                        -F "test_report=@artifacts/reports/test-pyramid-report.html"
                                '''
                            }
                        }
                    }
                    post {
                        always {
                            publishHTML([
                                reportDir: 'artifacts/reports',
                                reportFiles: 'test-pyramid-report.html',
                                reportName: 'Test Pyramid Report'
                            ])
                            archiveArtifacts artifacts: 'artifacts/reports/**'
                        }
                    }
                }
                
                stage('Auto-Remediation') {
                    agent { label 'remediation-agent' }
                    when {
                        expression { params.AUTO_REMEDIATE == true }
                    }
                    steps {
                        script {
                            echo "🔧 Applying automated remediation..."
                            unstash 'analysis-results'
                            
                            sh '''
                                mkdir -p artifacts/remediation
                                
                                # Apply security patches
                                python3 scripts/auto-remediate.py \
                                    --findings artifacts/analysis/risk-scores.json \
                                    --auto-fix-enabled \
                                    --output artifacts/remediation/remediation-log.json
                                
                                # Fix security groups
                                python3 scripts/fix-security-groups.py \
                                    --findings artifacts/cis/aws/prowler-results.json \
                                    --apply
                                
                                # Enable encryption
                                python3 scripts/enable-encryption.py \
                                    --findings artifacts/gdpr/encryption-report.json \
                                    --apply
                            '''
                        }
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: 'artifacts/remediation/**', allowEmptyArchive: true
                        }
                    }
                }
            }
        }
        
        // ====================================================================
        // STAGE 5: NOTIFICATION & ARCHIVAL
        // ====================================================================
        stage('Notification & Archival') {
            agent { label 'compliance-collector' }
            steps {
                script {
                    echo "📢 Sending notifications and archiving results..."
                    
                    // Archive to long-term storage (7+ years for compliance)
                    sh '''
                        # Upload to S3 with Object Lock for immutability
                        aws s3 cp artifacts/ \
                            s3://compliance-audit-trail/${SCAN_DATE}/ \
                            --recursive \
                            --storage-class GLACIER
                    '''
                }
            }
        }
    }
    
    post {
        success {
            script {
                // Send success notification via SNS
                sh """
                    aws sns publish \
                        --topic-arn \${SNS_TOPIC_ARN} \
                        --subject "✅ Compliance Pipeline Successful" \
                        --message "Job: ${env.JOB_NAME}
Build: ${env.BUILD_NUMBER}
Scan Date: ${SCAN_DATE}
Status: SUCCESS
View: ${env.BUILD_URL}"
                """
            }
        }
        
        failure {
            script {
                // Send failure notification via SNS
                sh """
                    aws sns publish \
                        --topic-arn \${SNS_TOPIC_ARN} \
                        --subject "❌ Compliance Pipeline Failed" \
                        --message "Job: ${env.JOB_NAME}
Build: ${env.BUILD_NUMBER}
Scan Date: ${SCAN_DATE}
Status: FAILED
View: ${env.BUILD_URL}"
                """
                
                // Create Jira ticket for critical issues
                withCredentials([usernamePassword(credentialsId: 'jira-creds', usernameVariable: 'JIRA_USER', passwordVariable: 'JIRA_PASS')]) {
                    sh '''
                        curl -X POST "$JIRA_URL/rest/api/2/issue" \
                            -H "Content-Type: application/json" \
                            -u "$JIRA_USER:$JIRA_PASS" \
                            -d '{
                                "fields": {
                                    "project": {"key": "SEC"},
                                    "summary": "Compliance Pipeline Failure - Build #'${BUILD_NUMBER}'",
                                    "description": "Critical compliance issues detected. Review pipeline results.",
                                    "issuetype": {"name": "Bug"},
                                    "priority": {"name": "Critical"}
                                }
                            }'
                    '''
                }
            }
        }
        
        always {
            script {
                // Cleanup workspace
                cleanWs()
            }
        }
    }
}
