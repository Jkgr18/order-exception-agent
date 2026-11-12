-- GUARDRAIL, layer 1 (database): the agent connects as agent_ro, which can only SELECT.
-- Even if the MCP server code had a bug, or a prompt injection tricked the model,
-- Postgres itself would refuse any INSERT / UPDATE / DELETE.
CREATE ROLE agent_ro LOGIN PASSWORD 'agent_ro_pw';   -- demo-only password
GRANT CONNECT ON DATABASE orders TO agent_ro;
GRANT USAGE ON SCHEMA public TO agent_ro;
GRANT SELECT ON orders TO agent_ro;
ALTER ROLE agent_ro SET default_transaction_read_only = on;
