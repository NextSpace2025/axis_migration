import pg from 'pg';

let pool;
export function query(sql, parameters) {
  if (!pool) {
    if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL is missing');
    const ca = process.env.DATABASE_CA_PEM;
    const url = new URL(process.env.DATABASE_URL);
    if (ca) {
      for (const param of ['ssl', 'sslmode', 'sslrootcert', 'sslcert', 'sslkey']) {
        url.searchParams.delete(param);
      }
    }
    pool = new pg.Pool({
      connectionString:url.href,
      ssl:ca ? {ca,rejectUnauthorized:true} : undefined,
      max:2,
      connectionTimeoutMillis:7000,
      statement_timeout:15000,
    });
  }
  return pool.query(sql, parameters);
}

export async function datasets(scope = null) {
  return (await query(
    'select id,label,description,default_table from axis_viewer.datasets where ($1::text is null or id=$1) order by id',
  [scope])).rows;
}

export async function dataset(id) {
  return (await query('select * from axis_viewer.datasets where id=$1',[id])).rows[0];
}

export async function tables(id) {
  const result = await query('select metadata from axis_viewer.tables where dataset=$1 order by name',[id]);
  return result.rows.map(row => row.metadata);
}
