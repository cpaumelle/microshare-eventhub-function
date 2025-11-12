# Security Architecture - Microshare to Azure Event Hub Forwarder

This document explains the security design, threat model, and best practices for the Microshare forwarder service.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Pull vs Push Security Model](#pull-vs-push-security-model)
3. [Authentication & Authorization](#authentication--authorization)
4. [Network Security](#network-security)
5. [Data Security](#data-security)
6. [Threat Model](#threat-model)
7. [Security Best Practices](#security-best-practices)
8. [Compliance Considerations](#compliance-considerations)

---

## Architecture Overview

### High-Level Data Flow

```
┌─────────────────┐         ┌──────────────┐         ┌────────────────┐
│  Microshare API │ ◄─HTTPS─┤  Forwarder   ├─HTTPS─► │ Azure Event Hub│
│  (SaaS)         │         │  VM (Client) │         │  (Azure PaaS)  │
└─────────────────┘         └──────────────┘         └────────────────┘
                                    │
                            ┌───────┴──────┐
                            │  Credentials  │
                            │  (.env file)  │
                            └──────────────┘
```

**Key Security Properties:**
- **Outbound-only traffic**: VM initiates all connections
- **No inbound firewall rules**: No exposed services
- **Certificate-based trust**: TLS 1.2+ for all connections
- **Credential isolation**: Secrets stored locally, not in code

---

## Pull vs Push Security Model

### Why Pull Architecture is More Secure

#### Traditional Push Model (LESS SECURE)
```
Microshare Server → [Internet] → Client Firewall → Client VM
                                       ↑
                              Requires IP whitelisting
                              Inbound rule: TCP 443
```

**Security Challenges:**
1. **IP Whitelisting Required**: Client must open firewall for Microshare IPs
2. **Dynamic IPs**: Cloud providers use dynamic IP ranges that change
3. **Broad IP Ranges**: Microsoft Azure IP ranges include thousands of addresses
4. **Attack Surface**: Inbound ports increase attack surface
5. **Blast Radius**: Any compromised service in Azure IP range could connect
6. **Network Trust**: Relies on network-layer security (IPs)

#### Modern Pull Model (MORE SECURE) ✓
```
Microshare Server ← [Internet] ← Client VM (no inbound rules)
                                     ↑
                              Certificate + Credentials
                              Outbound-only: TCP 443
```

**Security Benefits:**
1. **No Firewall Changes**: Client only needs outbound HTTPS (always allowed)
2. **No IP Whitelisting**: No dependency on source IP addresses
3. **Zero Inbound Attack Surface**: No services listening for connections
4. **Application-Layer Auth**: OAuth2 credentials + TLS certificates
5. **Standard SaaS Pattern**: Same as accessing Gmail, Office 365, etc.
6. **Defense in Depth**: Multiple layers (TLS + OAuth + API key)

---

## Authentication & Authorization

### 1. Microshare API Authentication

**Method**: OAuth 2.0 with username/password grant

```
Client → POST https://app.microshare.io/login
  └─ Credentials: username + password
  ← JWT token in PLAY_SESSION cookie

Client → GET https://api.microshare.io/share/...
  └─ Header: Authorization: Bearer <jwt_token>
```

**Security Features:**
- JWT tokens with expiration (typically 1 hour)
- Token caching to minimize auth requests
- Secure file storage (mode 0600)
- Automatic token refresh

**Credential Storage:**
```bash
/var/lib/microshare-forwarder/token_cache.json
Permissions: 0600 (rw-------)
Owner: root
```

### 2. Azure Event Hub Authentication

**Method**: Azure AD Service Principal with RBAC

```
Client → POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token
  └─ Credentials: client_id + client_secret
  ← Access token (expires in 1 hour)

Client → POST https://{namespace}.servicebus.windows.net/{hub}/messages
  └─ Header: Authorization: Bearer <access_token>
```

**Security Features:**
- Azure AD managed identities (production recommendation)
- Least-privilege RBAC: "Azure Event Hubs Data Sender" role only
- No shared access keys (SAS) used
- Automatic token management by Azure SDK
- Audit logs in Azure AD

**RBAC Permissions:**
```
Service Principal: microshare-forwarder-sp
Role: Azure Event Hubs Data Sender
Scope: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.EventHub/namespaces/{ns}
```

**Can do:**
- Send messages to Event Hub
- Get Event Hub metadata

**Cannot do:**
- Read messages from Event Hub
- Delete Event Hub
- Modify Event Hub configuration
- Access other Event Hubs in namespace

---

## Network Security

### 1. Outbound-Only Traffic

**Firewall Requirements:**
```bash
# REQUIRED (outbound HTTPS)
ALLOW TCP 443 → auth.microshare.io
ALLOW TCP 443 → api.microshare.io
ALLOW TCP 443 → login.microsoftonline.com
ALLOW TCP 443 → {namespace}.servicebus.windows.net

# NOT REQUIRED (no inbound rules)
# No inbound TCP/UDP on any port
```

### 2. TLS/SSL Configuration

**Requirements:**
- TLS 1.2 minimum (enforced by both Microshare and Azure)
- Certificate validation enabled (default in Python requests library)
- Strong cipher suites only

**Python Configuration (automatic):**
```python
import requests

# Certificate validation ON (default)
response = requests.get(url, verify=True)

# TLS 1.2+ enforced by server
# No code changes needed
```

### 3. Network Isolation Options

#### Option A: Public VM (Default)
```
[VM with Public IP] → Internet → Microshare/Azure
```
- Simple setup
- No additional cost
- Suitable for most deployments

#### Option B: Private VM with NAT Gateway
```
[VM Private Subnet] → NAT Gateway → Internet → Microshare/Azure
```
- No public IP on VM
- Static outbound IP (if needed for audit logs)
- +$35/month for NAT Gateway

#### Option C: Private VM with VPN/ExpressRoute
```
[VM Private Subnet] → Azure Firewall/VPN → Internet → Microshare/Azure
```
- Maximum isolation
- Centralized logging
- Highest cost (ExpressRoute)

**Recommendation**: Option A (public VM) is sufficient for most use cases since:
- No inbound traffic accepted
- All traffic is TLS encrypted
- Application-layer authentication required
- Attack surface is minimal

---

## Data Security

### 1. Data in Transit

**Encryption:**
- All data encrypted with TLS 1.2+ (AES-256-GCM)
- Certificate pinning not required (public CAs trusted)
- Perfect forward secrecy (PFS) enabled

**Validation:**
```bash
# Test Microshare API TLS
openssl s_client -connect api.microshare.io:443 -tls1_2

# Should show:
# Protocol: TLSv1.2 or TLSv1.3
# Cipher: ECDHE-RSA-AES256-GCM-SHA384 (or similar)
```

### 2. Data at Rest

**Credentials (.env file):**
```bash
Location: /opt/occupancy-snapshot/.env
Permissions: 0600 (rw-------)
Owner: root:root
Encryption: None (relies on disk encryption)
```

**Recommendation**: Enable Azure Disk Encryption
```bash
az vm encryption enable \
  --resource-group $RESOURCE_GROUP \
  --name $VM_NAME \
  --disk-encryption-keyvault <keyvault-name>
```

**Token Cache:**
```bash
Location: /var/lib/microshare-forwarder/token_cache.json
Permissions: 0600 (rw-------)
Owner: root:root
Contents: JWT tokens (expires in 1 hour)
```

**State File:**
```bash
Location: /var/lib/microshare-forwarder/state.json
Permissions: 0644 (rw-r--r--)
Owner: root:root
Contents: Statistics only (no sensitive data)
```

### 3. Data in Memory

**During Processing:**
- Credentials loaded from .env at startup
- Tokens cached in memory
- Snapshot data held temporarily during forwarding
- No persistent memory dumps

**After Processing:**
- Credentials remain in memory (service runs as oneshot)
- No data persisted to disk except state.json
- Logs may contain metadata (no credentials or payload data)

### 4. Logging & Audit Trail

**What is Logged:**
- Timestamps of fetch operations
- Count of snapshots fetched/sent
- API response codes
- Error messages (sanitized)

**What is NOT Logged:**
- Passwords or tokens
- Payload data
- Device IDs or location details

**Log Locations:**
```bash
# Systemd journal
/var/log/journal/...
Retention: 7 days (configurable)

# Azure Event Hub audit
Azure Portal → Event Hub → Diagnostic Settings
Send to Log Analytics workspace
```

---

## Threat Model

### Threats Addressed

#### 1. Network Eavesdropping
**Threat**: Attacker intercepts traffic to steal data or credentials
**Mitigation**: TLS 1.2+ encryption on all connections
**Residual Risk**: Negligible (requires compromising CA or breaking AES-256)

#### 2. Credential Theft
**Threat**: Attacker gains access to VM and steals credentials
**Mitigation**:
- File permissions (0600 on .env)
- Azure Disk Encryption
- Regular security updates
**Residual Risk**: Low (requires VM compromise)

#### 3. Man-in-the-Middle (MITM)
**Threat**: Attacker intercepts and modifies traffic
**Mitigation**: Certificate validation, TLS, HTTPS-only
**Residual Risk**: Negligible (requires compromising CA)

#### 4. Replay Attacks
**Threat**: Attacker captures and replays API requests
**Mitigation**:
- Short-lived tokens (1 hour expiration)
- Deduplication logic (snapshot IDs)
- Timestamp validation
**Residual Risk**: Very Low (limited time window, data already sent)

#### 5. Denial of Service (DoS)
**Threat**: Attacker overwhelms service or API
**Mitigation**:
- Rate limiting (poll once per hour)
- Retry logic with backoff
- Azure Event Hub throttling
**Residual Risk**: Low (attacker would need VM access)

#### 6. Privilege Escalation
**Threat**: Attacker escalates from service account to admin
**Mitigation**:
- Service runs as root (systemd requirement)
- No sudo/privileged commands in code
- Regular security updates
**Residual Risk**: Medium (service runs as root)

### Threats NOT Addressed

#### 1. VM Compromise
If attacker gains root access to VM, they can:
- Read credentials from .env file
- Impersonate service to send data to Event Hub
- Modify code to exfiltrate data

**Mitigation (defense in depth):**
- Keep VM patched and updated
- Disable SSH password authentication
- Use Azure Bastion instead of public SSH
- Enable Azure Security Center recommendations
- Rotate credentials regularly

#### 2. Insider Threats
If attacker has Azure subscription access, they can:
- Read Event Hub data
- Modify VM or service configuration
- Access credentials via Azure Portal

**Mitigation:**
- Use Azure RBAC with least privilege
- Enable Azure AD Privileged Identity Management (PIM)
- Audit Azure AD sign-in logs
- Separate dev/prod environments

---

## Security Best Practices

### 1. Credential Management

**DO:**
- Use Azure Key Vault for credential storage (advanced)
- Rotate credentials every 90 days
- Use managed identities when possible
- Restrict .env file permissions (0600)

**DON'T:**
- Commit .env to version control
- Share credentials via email/chat
- Use the same credentials across environments
- Log credentials

### 2. Network Configuration

**DO:**
- Use private subnet with NAT Gateway (production)
- Enable Azure DDoS Protection Standard
- Configure NSG with explicit deny rules
- Use Azure Firewall for centralized logging

**DON'T:**
- Open inbound ports on NSG
- Use public IPs for production VMs
- Disable certificate validation
- Use insecure protocols (HTTP, FTP, Telnet)

### 3. VM Hardening

**DO:**
```bash
# Disable password authentication
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# Enable automatic security updates
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# Configure firewall (UFW)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from <your-ip> to any port 22  # SSH from your IP only
sudo ufw enable

# Install fail2ban
sudo apt install -y fail2ban
```

**DON'T:**
- Use default passwords
- Run unnecessary services
- Expose SSH to 0.0.0.0/0
- Disable firewall

### 4. Monitoring & Alerting

**DO:**
```bash
# Enable Azure Monitor
az vm extension set \
  --resource-group $RESOURCE_GROUP \
  --vm-name $VM_NAME \
  --name AzureMonitorLinuxAgent \
  --publisher Microsoft.Azure.Monitor

# Create alert for service failures
az monitor metrics alert create \
  --name "Forwarder-ServiceFailed" \
  --resource-group $RESOURCE_GROUP \
  --condition "count Failed_Units > 0"
```

**DON'T:**
- Ignore failed systemd units
- Disable audit logs
- Ignore high duplicate counts
- Ignore pagination warnings

---

## Compliance Considerations

### GDPR (General Data Protection Regulation)

**Data Processed:**
- Occupancy snapshots (sensor data)
- Device IDs
- Location identifiers (building/floor/room)
- Timestamps

**Personal Data:**
- Likely **NO** personal data (sensors only detect presence, not identity)
- Device IDs are not linked to individuals
- Location data is aggregate (room-level, not desk-level)

**Recommendations:**
- Document data flows in GDPR Article 30 records
- Ensure data retention policies (Event Hub: 1 day default)
- Review with Data Protection Officer (DPO) if needed

### HIPAA (Health Insurance Portability and Accountability Act)

**Not Applicable**: Occupancy data is not Protected Health Information (PHI)

### SOC 2 (Service Organization Control)

**Relevant Controls:**
- CC6.1: Logical and physical access controls (Azure RBAC, file permissions)
- CC6.6: Encryption in transit (TLS 1.2+)
- CC6.7: Encryption at rest (Azure Disk Encryption optional)
- CC7.2: Monitoring (systemd logs, Azure Monitor)

---

## Incident Response

### Credential Compromise

If credentials are compromised:

1. **Immediate Actions:**
```bash
# Rotate Microshare password
# (Contact Microshare support)

# Rotate Azure Service Principal secret
az ad sp credential reset --id $AZURE_CLIENT_ID

# Update .env file with new credentials
sudo nano /opt/occupancy-snapshot/.env

# Restart service
sudo systemctl restart microshare-forwarder.timer
```

2. **Investigation:**
```bash
# Check Azure AD sign-in logs
az monitor activity-log list \
  --resource-group $RESOURCE_GROUP \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --query "[?contains(operationName.value, 'Microsoft.EventHub')]"

# Check Event Hub metrics for anomalies
# (Unexpected spike in messages)
```

3. **Post-Incident:**
- Document timeline and root cause
- Update procedures to prevent recurrence
- Consider moving to Azure Key Vault

### VM Compromise

If VM is compromised:

1. **Immediate Actions:**
```bash
# Isolate VM (stop but don't delete)
az vm stop --resource-group $RESOURCE_GROUP --name $VM_NAME

# Disable Service Principal
az ad sp update --id $AZURE_CLIENT_ID --set accountEnabled=false

# Take disk snapshot for forensics
az snapshot create \
  --resource-group $RESOURCE_GROUP \
  --name "${VM_NAME}-forensics-$(date +%Y%m%d)" \
  --source $(az vm show --resource-group $RESOURCE_GROUP --name $VM_NAME --query storageProfile.osDisk.managedDisk.id -o tsv)
```

2. **Investigation:**
- Analyze disk snapshot
- Check systemd journal for unauthorized executions
- Review Azure activity logs
- Check Event Hub for data exfiltration

3. **Recovery:**
- Deploy new VM from clean image
- Rotate all credentials
- Restore configuration from version control
- Resume service after validation

---

## Security Checklist

### Pre-Deployment
- [ ] Credentials stored in .env (not in code)
- [ ] File permissions: .env (0600), scripts (0755)
- [ ] Azure Service Principal created with least privilege
- [ ] NSG configured with no inbound rules
- [ ] VM OS patched to latest
- [ ] SSH password authentication disabled
- [ ] Firewall (UFW) enabled

### Post-Deployment
- [ ] Test manual execution (sudo python3 -m app.forwarder)
- [ ] Verify systemd service runs successfully
- [ ] Check Event Hub receives data
- [ ] Configure Azure Monitor alerts
- [ ] Document credentials in password manager
- [ ] Schedule 90-day credential rotation
- [ ] Enable Azure Security Center recommendations

### Ongoing Maintenance
- [ ] Monthly: Review systemd logs for errors
- [ ] Monthly: Check state file for anomalies
- [ ] Quarterly: Rotate credentials
- [ ] Quarterly: Update Python dependencies
- [ ] Annually: Review security architecture
- [ ] As needed: Apply VM security updates

---

## Contact

For security concerns or to report a vulnerability:
- **Internal**: Contact your security team
- **Azure Issues**: Azure Support via Azure Portal

**Do NOT** report security issues in public forums or GitHub issues.

---

## References

- [Azure Event Hubs Security](https://docs.microsoft.com/en-us/azure/event-hubs/authenticate-application)
- [OAuth 2.0 Threat Model](https://tools.ietf.org/html/rfc6819)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [Azure Security Best Practices](https://docs.microsoft.com/en-us/azure/security/fundamentals/best-practices-and-patterns)
