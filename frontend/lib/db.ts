import { Pool } from 'pg';

// Initialize the Postgres connection pool using the string from .env.local
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

export default pool;