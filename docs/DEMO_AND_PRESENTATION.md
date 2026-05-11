# PHQ Intelligence Bot — Demo Guide & Presentation Script

---

## Part 1: Local Demo (Apne Laptop Par)

### Prerequisites (ek baar install karna hai)
```bash
cd /path/to/PHQ
pip install fastapi "uvicorn[standard]"
```

### Demo Start Karna
```bash
python scripts/run_demo.py
```

Browser automatically opens at `http://localhost:8000`

### Demo Queries (Copy-paste karo)

| Query | Kya dikhega |
|-------|-------------|
| `Smart meter protest ke baare mein batao` | Full incident summary with evidence |
| `Agra mein kya hua smart meter ko lekar?` | Agra FIR + district-specific data |
| `Lucknow mein kya situation hai?` | Lucknow protest details |
| `Sentiment analysis karo` | 87.3% negative sentiment breakdown |
| `AAP ka role kya hai is protest mein?` | Political analysis with coordination evidence |

### Sample Report Dekhna
Browser mein jaao: `http://localhost:8000/api/v2/reports/RPT-DEMO/html`

Ya chat mein pucho: "Report generate karo"

---

## Part 2: Government Secretary Ko Samjhana

### Opening (30 seconds)
> "Sir, aapka social media monitoring team abhi manually hazaron posts check karta hai 
> aur phir yeh report banata hai. Hum ek AI bot bana rahe hain jo yeh kaam 
> automatically karta hai — 24x7. Aap ya koi bhi officer apne phone se Hindi mein 
> puchh sakte hain ki Lucknow mein kya ho raha hai, turant answer milega."

### Live Demo Script (5 minutes)

**Step 1** — Chat open karo, type karo:
> "Smart meter protest ke baare mein batao"

Point out:
- Answer Hindi mein aaya
- Evidence cite kiya: [1], [2], [3]
- Confidence score dikhata hai (89%)
- District detect kiya automatically
- Response time: ~1 second

**Step 2** — Next query:
> "Agra mein kya hua?"

Point out:
- Previous context yaad rakha (follow-up question samjha)
- FIR details, exact dates, names mention kiye
- "Official Report" sources ★ se mark hain — sabse credible

**Step 3** — Report dikhao:
`http://localhost:8000/api/v2/reports/RPT-DEMO/html`

Point out:
- Exactly wahi format jo aapki team manually banati thi
- Ab yeh **automatically daily generate hoti hai** (8 AM IST)
- **Email bhi jaati hai** configured recipients ko
- **Spike alert**: agar kisi issue par 50+ posts 6 ghante mein aaye, turant alert

### Key Points for Secretary

1. **Koi naya data collect nahi ho raha** — Matrix ka existing data use ho raha hai
2. **Secure** — Same JWT token jo Matrix mein login karte hain, wahi yahan bhi chalega
3. **Hindi + English** dono mein kaam karta hai
4. **Evidence-based** — Hallucination nahi karta, sirf database ka data dikhata hai
5. **24x7 monitoring** — Raat ko bhi spike detect hoga, alert aayega

---

## Part 3: Matrix Dev Team Ko Samjhana (Technical)

### Architecture in 1 Slide

```
Matrix MySQL DB  ──→  Embedding Sync  ──→  Qdrant (Vector DB)
(analyzed_data,            (every 60s)        (phq_events,
 topic,                                        phq_topics)
 district_report)                                  │
                                                   ↓
Officer  ──→  Chat Widget  ──→  FastAPI  ──→  Query Agent
(Hindi/Eng)  (Matrix page)   (aibot.matrixupp.com)  (LLM + Qdrant search)
                                    │
                               Report Generator
                               (daily 8AM + spike)
                                    │
                               Email Notification
```

### Integration Steps (Dev Team ke liye)

**Step 1**: Bot deploy karo on H200 server
```bash
git clone https://github.com/prashmalv/phq.git
cd phq
pip install -r backend/requirements.txt
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

**Step 2**: Subdomain point karo
- `aibot.matrixupp.com` → H200 server IP (port 8000)
- Nginx config:
```nginx
server {
    server_name aibot.matrixupp.com;
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
    }
}
```

**Step 3**: Widget add karo Matrix base template mein (ek line)
```html
<script src="https://aibot.matrixupp.com/static/widget/chat-widget.js"
        data-api="https://aibot.matrixupp.com"
        data-token-fn="getMatrixToken"></script>
<script>
  window.getMatrixToken = () => localStorage.getItem('matrix_jwt') || '';
</script>
```

**Step 4**: Email notifications configure karo (optional)
```
# .env file mein add karo:
REPORT_EMAIL_RECIPIENTS=["dgp@uppolice.gov.in","secretary@uppolice.gov.in"]
SMTP_USER=phq.notifications@gmail.com
SMTP_PASSWORD=app_password_here
```

### API Endpoints (3 hi kaam ke hain)

| Endpoint | Use |
|----------|-----|
| `POST /api/v2/chat/query` | Chat query bhejo, answer lo |
| `GET /api/v2/reports/` | Sabhi reports ki list |
| `GET /api/v2/reports/{id}/html` | Full HTML report |

**Auth**: Matrix JWT token waise ka waisa use hoga — `Authorization: Bearer <token>`

### What Matrix Team Needs to Do

- [ ] `aibot.matrixupp.com` DNS point karo H200 server pe
- [ ] Nginx/Apache reverse proxy set up karo port 8000 pe
- [ ] Widget script tag add karo base HTML template mein
- [ ] `window.getMatrixToken` function implement karo (JWT fetching)
- [ ] ZeroTier VPN ensure karo so bot can reach MySQL (10.242.71.180)
- [ ] Qdrant Docker run karo: `docker run -p 6333:6333 qdrant/qdrant`

---

## Part 4: FAQ — Sawal Jo Pooche Ja Sakte Hain

**Q: Kya yeh existing Matrix data ko affect karega?**
A: Bilkul nahi. Bot sirf *read* karta hai MySQL se. Koi write operation nahi hai.

**Q: Agar LLM model nahi hai to kya hoga?**
A: Bot mock mode mein run karega — data dikh jaayega lekin AI narrative nahi likhega. 
   Client ke H200 server par GPU hai, to Llama 3 model download karke full AI enable ho jaayega.

**Q: Report automatically kis time generate hogi?**
A: Roz subah 8 AM IST par last 7 days ki report generate hogi.
   Agar 6 ghante mein 50+ posts aaye kisi topic par, turant spike alert report bhi generate hogi.

**Q: Email kahan jaayegi?**
A: `.env` mein `REPORT_EMAIL_RECIPIENTS` mein jo email IDs configure hongi, wahan.
   Senior officers / DGP ka email set kar sakte hain.

**Q: Kya officers ka chat history safe hai?**
A: Haan. Har officer ka chat history sirf uske JWT token se accessible hai.
   Ek officer doosre ka history nahi dekh sakta.

**Q: Kitni languages support karti hai?**
A: Hindi (Devanagari), English, aur mixed Hinglish — teeno mein query kar sakte hain.

---

## Part 5: Next Steps After Demo Approval

1. **Production Deploy** (1 din): H200 server par uvicorn + nginx setup
2. **LLM Download** (2-3 ghante): Llama 3 8B model download (4.5 GB)
3. **Backfill** (1 raat): Historical data embed karna Qdrant mein
   ```bash
   python -m backend.sync.embedding_sync backfill
   ```
4. **Matrix Widget Integration** (1-2 ghante): Dev team adds the script tag
5. **UAT** (2-3 din): Officers test karte hain, feedback incorporate karo
6. **Go Live**: Full production
