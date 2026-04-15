# Google Connect UI Backlog

Status: Planned (deferred implementation)

## Goal

Add a UI "Connect Google Docs" button that opens Google OAuth consent so each user links their own Google account.

## Target UX

1. User clicks `Connect Google Docs`.
2. Frontend opens popup/redirect to backend OAuth start endpoint.
3. Google consent screen appears; user chooses their own Gmail account.
4. Backend receives callback, exchanges code for user tokens, stores tokens for that user only.
5. UI shows connector status as connected.

## Important Architecture Note

1. The product still needs one Google Cloud OAuth app configured by us:
   - `GOOGLE_OAUTH_CLIENT_ID`
   - `GOOGLE_OAUTH_CLIENT_SECRET`
2. End users never get access to our Gmail/docs by default.
3. Each user only authorizes and accesses their own Google Docs data through their own token set.

## Implementation Later Checklist

1. Frontend connect button and popup flow.
2. OAuth callback success/failure UI states.
3. Connector status refresh in UI.
4. Reconnect/disconnect controls.
