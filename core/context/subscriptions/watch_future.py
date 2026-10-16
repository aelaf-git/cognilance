"""Future: Gmail Watch API + Google Cloud Pub/Sub push notifications.

Phase 2 replaces polling in subscriptions/ticker.py with:
- users.watch on Gmail inbox
- POST /integrations/gmail/push webhook
- watch renewal before 7-day expiry
- gmail.modify scope

See: https://developers.google.com/gmail/api/guides/push
"""
