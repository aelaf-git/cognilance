-- CreateTable
CREATE TABLE "api_keys" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "key_prefix" TEXT NOT NULL,
    "key_hash" TEXT NOT NULL,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "agents" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "owner_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "description" TEXT NOT NULL DEFAULT '',
    "skills" TEXT NOT NULL DEFAULT '[]',
    "visibility" TEXT NOT NULL DEFAULT 'public',
    "tags" TEXT NOT NULL DEFAULT '[]',
    "version" TEXT NOT NULL DEFAULT '0.1.0',
    "online" BOOLEAN NOT NULL DEFAULT true,
    "last_heartbeat" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" DATETIME NOT NULL,
    CONSTRAINT "agents_owner_id_fkey" FOREIGN KEY ("owner_id") REFERENCES "api_keys" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "trace_events" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "owner_id" TEXT,
    "trace_id" TEXT NOT NULL,
    "task_id" TEXT NOT NULL,
    "parent_task_id" TEXT,
    "depth" INTEGER NOT NULL DEFAULT 0,
    "agent_name" TEXT NOT NULL DEFAULT '',
    "type" TEXT NOT NULL,
    "text" TEXT NOT NULL DEFAULT '',
    "data" TEXT NOT NULL DEFAULT '{}',
    "timestamp" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "trace_events_owner_id_fkey" FOREIGN KEY ("owner_id") REFERENCES "api_keys" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "trace_index" (
    "trace_id" TEXT NOT NULL PRIMARY KEY,
    "owner_id" TEXT,
    "first_event_at" DATETIME NOT NULL,
    "last_event_at" DATETIME NOT NULL,
    "event_count" INTEGER NOT NULL DEFAULT 1,
    "updated_at" DATETIME NOT NULL,
    CONSTRAINT "trace_index_owner_id_fkey" FOREIGN KEY ("owner_id") REFERENCES "api_keys" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateIndex
CREATE INDEX "api_keys_key_prefix_idx" ON "api_keys"("key_prefix");

-- CreateIndex
CREATE INDEX "agents_owner_id_idx" ON "agents"("owner_id");

-- CreateIndex
CREATE INDEX "agents_visibility_online_idx" ON "agents"("visibility", "online");

-- CreateIndex
CREATE INDEX "agents_last_heartbeat_idx" ON "agents"("last_heartbeat");

-- CreateIndex
CREATE INDEX "trace_events_trace_id_idx" ON "trace_events"("trace_id");

-- CreateIndex
CREATE INDEX "trace_events_owner_id_idx" ON "trace_events"("owner_id");

-- CreateIndex
CREATE INDEX "trace_events_trace_id_timestamp_idx" ON "trace_events"("trace_id", "timestamp");

-- CreateIndex
CREATE INDEX "trace_index_owner_id_idx" ON "trace_index"("owner_id");
