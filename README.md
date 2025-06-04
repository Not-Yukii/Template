# Template

This project includes a simple FastAPI application that manages users and chat conversations backed by a PostgreSQL database.

## Running the application

Install the dependencies:

```bash
pip install -r requirements.txt
```

Start the API with `uvicorn`:

```bash
uvicorn app.main:app --reload
```

The API now exposes the following endpoints:

- `POST /register` - Create a new user with `email` and `password`. The password is hashed before storing.
- `POST /login` - Authenticate with `email` and `password` and receive a token.
- `GET /conversations` - List conversations for the authenticated user (`Authorization: Bearer <token>`).
- `GET /chat/{id}` - Retrieve all messages for a conversation.
- `POST /send` - Send a message to a conversation or start a new one.

Make sure a PostgreSQL server is running and accessible at `postgresql://user:password@localhost/test` or update the `DATABASE_URL` environment variable accordingly.