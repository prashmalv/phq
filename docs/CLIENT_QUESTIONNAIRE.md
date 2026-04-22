# Client Onboarding Questionnaire
## PHQ Government Intelligence Bot — Information Required Before Go-Live
**To be filled by: IT & Electronics Department, Police HQ, Uttar Pradesh**

---

## SECTION 1: Infrastructure & Servers

| # | Question | Answer |
|---|----------|--------|
| 1.1 | How many on-premise servers are available? (CPU cores, RAM, storage per server) | |
| 1.2 | Is GPU hardware available? (for faster LLM inference) | |
| 1.3 | What is the OS on the servers? (Ubuntu 22.04 preferred) | |
| 1.4 | Is there an internal network / VLAN for the system? | |
| 1.5 | What is the internet connectivity from the server room? (bandwidth for data ingestion) | |
| 1.6 | Is an air-gapped deployment required (zero internet), or is outbound-only internet allowed? | |
| 1.7 | Who is the system admin / DevOps point of contact? | |

---

## SECTION 2: Social Media API Access

> **Note:** Without API access, the system can only ingest news feeds. Social media ingestion requires API credentials from each platform.

| # | Question | Answer |
|---|----------|--------|
| 2.1 | Does PHQ have an existing **Twitter/X Developer Account**? (Required for tweet search) | |
| 2.2 | What is the Twitter API access tier? (Free / Basic / Pro / Enterprise) | |
| 2.3 | Is a **Facebook Graph API** access token available for public pages/posts? | |
| 2.4 | Is there access to **Instagram Basic Display API** or Business API? | |
| 2.5 | Are there any **existing social listening tools** already in use? (e.g. Brandwatch, Sprinklr) | |
| 2.6 | Are there any **official government social media handles** to monitor? (list them) | |

---

## SECTION 3: News & Government Data Sources

| # | Question | Answer |
|---|----------|--------|
| 3.1 | Which **Hindi/English news portals** should be monitored? (provide URL list) | |
| 3.2 | Are there any **UP-specific regional portals** beyond Amar Ujala / Dainik Jagran? | |
| 3.3 | Is there an **internal FIR / incident reporting system** with API or DB access? | |
| 3.4 | Are **district administration logs** available in digital format? (CSV / API / DB) | |
| 3.5 | Is there a **government news portal** (e.g. PIB UP, CMO UP) to ingest? | |
| 3.6 | Are **police press releases** published anywhere digitally? | |
| 3.7 | Is historical incident data available? (last 5 years preferred — format: Excel/CSV/DB) | |

---

## SECTION 4: User Access & Roles

| # | Question | Answer |
|---|----------|--------|
| 4.1 | How many officers will use the system? (initial rollout) | |
| 4.2 | What are the roles? (e.g. DGP, IGP, SP, DM, Data Analyst) | |
| 4.3 | Should different roles see different data? (e.g. DM can only see their district) | |
| 4.4 | Is there an existing **LDAP / Active Directory** for single sign-on? | |
| 4.5 | Should login be through a govt email domain? (e.g. @uppolice.gov.in) | |
| 4.6 | Should query audit logs be visible to a senior officer/admin? | |
| 4.7 | Who approves adding new users to the system? | |

---

## SECTION 5: Language & Query Requirements

| # | Question | Answer |
|---|----------|--------|
| 5.1 | Primary query language for officers? (Hindi / English / Both) | |
| 5.2 | Should answers be given in Hindi, English, or match the query language? | |
| 5.3 | Are there Urdu-language sources or officers who query in Urdu? | |
| 5.4 | Should the system support voice input? (Phase 2 optional) | |

---

## SECTION 6: Alert & Notification Requirements

| # | Question | Answer |
|---|----------|--------|
| 6.1 | Should the system **auto-alert** officers for high-priority events? | |
| 6.2 | How should alerts be delivered? (SMS / email / internal app / WhatsApp) | |
| 6.3 | What triggers an alert? (e.g. "violence in any district", "stampede keyword spike") | |
| 6.4 | Who receives which alert? (all alerts to DGP, district alerts to respective SP?) | |
| 6.5 | Is there an existing **police control room communication system** to integrate with? | |

---

## SECTION 7: Data Retention & Compliance

| # | Question | Answer |
|---|----------|--------|
| 7.1 | How long should event data be retained? (1 year / 5 years / indefinitely) | |
| 7.2 | Is there a data classification policy for the content stored? | |
| 7.3 | Are there any **IT Act / PDPB compliance requirements** to follow? | |
| 7.4 | Should personally identifiable information (PII) from social media be anonymized before storage? | |
| 7.5 | Who is the designated **data controller** for this system? | |
| 7.6 | Is a third-party security audit required before go-live? | |

---

## SECTION 8: LLM Model

| # | Question | Answer |
|---|----------|--------|
| 8.1 | Is the Llama 3 model download (~5GB) approved for use on govt infrastructure? | |
| 8.2 | Is there a preferred Hindi-specific LLM? (e.g. Airavata, Krutrim) | |
| 8.3 | Should the model be fine-tuned on UP-specific terminology? (adds ~2 weeks effort) | |
| 8.4 | Are queries to an external LLM API (Claude/GPT) acceptable, or strictly on-premise? | |

---

## SECTION 9: Phase 1 Pilot

| # | Question | Answer |
|---|----------|--------|
| 9.1 | Which **3–5 officers** will participate in the pilot? | |
| 9.2 | Which **2–3 districts** should be prioritized for initial data? | |
| 9.3 | What are the **top 10 query types** officers most need to answer? | |
| 9.4 | Is there a **UAT (User Acceptance Testing) process** before formal launch? | |
| 9.5 | What is the **go-live deadline** for Phase 1? | |

---

## Data You Need to Provide to the Development Team

Please arrange to share the following before development begins:

1. **Historical incident data** — CSV or DB export of past incidents (last 3–5 years)
2. **News portal RSS URLs** for all UP regional portals you want monitored
3. **Twitter API credentials** (bearer token + app keys)
4. **Server SSH access** for infrastructure setup
5. **List of politician/leader names** to track in the Knowledge Graph
6. **List of sensitive locations** (pilgrimage sites, border areas, communally sensitive areas)
7. **Official hashtags/handles** used by UP Police / CMO / district administration

---

*Please return the filled questionnaire to the development team before the kickoff meeting.*
*Contact: [your contact here]*
