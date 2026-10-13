create schema api;

create role web_anon nologin;

grant usage on schema api to web_anon;
-- Read-only access to every table, view and sequence in every schema,
-- including ones created later
grant pg_read_all_data to web_anon;

create role authenticator noinherit login password 'marxengelsyaoi69';
grant web_anon to authenticator;
