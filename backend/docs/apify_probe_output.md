# Temporary Apify Actor Probe

- Actor ID: `UL2325zphnyxDYpsp`
- Tested URL: `https://www.upwork.com/jobs/~022041005560876380510?referrer_url_path=%2Fnx%2Fsearch%2Fjobs%2Fdetails%2F~022041005560876380510`

## Results

### queries_with_job_url

- HTTP status: `201`
- Parsed summary: `{"success": true, "total_jobs_scraped": 0, "error": null, "queries_processed": ["https://www.upwork.com/jobs/~022041005560876380510?referrer_url_path=%2Fnx%2Fsearch%2Fjobs%2Fdetails%2F~022041005560876380510"]}`
- Payload:
```json
{
  "queries": [
    "https://www.upwork.com/jobs/~022041005560876380510?referrer_url_path=%2Fnx%2Fsearch%2Fjobs%2Fdetails%2F~022041005560876380510"
  ]
}
```
- Raw response preview:
```json
[{
  "summary": true,
  "total_jobs_scraped": 0,
  "queries_processed": [
    "https://www.upwork.com/jobs/~022041005560876380510?referrer_url_path=%2Fnx%2Fsearch%2Fjobs%2Fdetails%2F~022041005560876380510"
  ],
  "item_limit": 100,
  "scraping_completed_at": "2026-04-06 07:46:29",
  "success": true
}]
```

### queries_with_job_url_no_apify_proxy

- HTTP status: `201`
- Parsed summary: `{"success": true, "total_jobs_scraped": 0, "error": null, "queries_processed": ["https://www.upwork.com/jobs/~022041005560876380510?referrer_url_path=%2Fnx%2Fsearch%2Fjobs%2Fdetails%2F~022041005560876380510"]}`
- Payload:
```json
{
  "queries": [
    "https://www.upwork.com/jobs/~022041005560876380510?referrer_url_path=%2Fnx%2Fsearch%2Fjobs%2Fdetails%2F~022041005560876380510"
  ],
  "proxyConfiguration": {
    "useApifyProxy": false
  }
}
```
- Raw response preview:
```json
[{
  "summary": true,
  "total_jobs_scraped": 0,
  "queries_processed": [
    "https://www.upwork.com/jobs/~022041005560876380510?referrer_url_path=%2Fnx%2Fsearch%2Fjobs%2Fdetails%2F~022041005560876380510"
  ],
  "item_limit": 100,
  "scraping_completed_at": "2026-04-06 07:47:11",
  "success": true
}]
```

### queries_with_search_url

- HTTP status: `201`
- Parsed summary: `{"success": null, "total_jobs_scraped": null, "error": null, "queries_processed": null}`
- Payload:
```json
{
  "queries": [
    "https://www.upwork.com/freelance-jobs/automation/"
  ]
}
```
- Raw response preview:
```json
[{
  "title": null,
  "url": null,
  "datePosted": null,
  "employmentType": null,
  "description": "",
  "skills": "",
  "hiringOrganization": null,
  "jobLocation": null,
  "applicantLocationRequirements": []
},
{
  "summary": true,
  "total_jobs_scraped": 1,
  "queries_processed": [
    "https://www.upwork.com/freelance-jobs/automation/"
  ],
  "item_limit": 100,
  "scraping_completed_at": "2026-04-06 07:48:24",
  "success": true
}]
```

## Verdict

- Actor did not return usable scraped job data for tested cases.

Note: This is a temporary diagnostic script/report.