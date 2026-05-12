# Autonomous Optimization Skill

## Core Principles
- No subjective grading — mathematical evaluation criteria always
- No interfering with production — all testing via shadow traffic
- Always calculate cost per 1M tokens for primary and fallback paths
- Halt on anomaly — 500% traffic spike = circuit breaker + alert

## Shadow Testing
- Route 5% of traffic to candidate model
- Grade using LLM-as-a-Judge methodology
- Scoring: 5 pts JSON formatting, 3 pts latency, -10 pts hallucination
- Auto-promote when candidate wins 3 consecutive evaluation windows

## Circuit Breaker States
- Closed: Normal operation, tracking failure rate
- Open: All requests routed to fallback (triggered at threshold)
- Half-Open: Limited test traffic to check recovery

## FinOps Rules
- Every API call must have: timeout, retry cap, cheaper fallback
- No open-ended retry loops or unbounded API calls
- Budget alerts at 50%, 75%, 90%, 100% of monthly limit
- Cost anomaly detection: >200% daily average = alert
