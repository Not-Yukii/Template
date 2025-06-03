# Template

This project includes a simple FastAPI application that connects to a PostgreSQL database and manages user accounts.

## Running the application

Install the dependencies:

```bash
pip install -r requirements.txt
```

Start the API with `uvicorn`:

```bash
uvicorn app.main:app --reload
```

The API provides two endpoints:

- `POST /register` - Create a new user with `email` and `password`.
- `POST /login` - Authenticate a user with `email` and `password`.

Make sure a PostgreSQL server is running and accessible at `postgresql://user:password@localhost/test` or update `DATABASE_URL` in `app/main.py` accordingly.
