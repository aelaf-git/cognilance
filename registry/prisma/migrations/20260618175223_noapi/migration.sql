/*
  Warnings:

  - You are about to drop the `api_keys` table. If the table is not empty, all the data it contains will be lost.
  - You are about to drop the column `owner_id` on the `agents` table. All the data in the column will be lost.
  - You are about to drop the column `owner_id` on the `trace_events` table. All the data in the column will be lost.
  - You are about to drop the column `owner_id` on the `trace_index` table. All the data in the column will be lost.

*/
-- DropIndex
DROP INDEX "api_keys_key_prefix_idx";

-- DropTable
PRAGMA foreign_keys=off;
DROP TABLE "api_keys";
PRAGMA foreign_keys=on;

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_agents" (
    "id" TEXT NOT NULL PRIMARY KEY,
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
    "updated_at" DATETIME NOT NULL
);
INSERT INTO "new_agents" ("created_at", "description", "id", "last_heartbeat", "name", "online", "skills", "tags", "updated_at", "url", "version", "visibility") SELECT "created_at", "description", "id", "last_heartbeat", "name", "online", "skills", "tags", "updated_at", "url", "version", "visibility" FROM "agents";
DROP TABLE "agents";
ALTER TABLE "new_agents" RENAME TO "agents";
CREATE INDEX "agents_visibility_online_idx" ON "agents"("visibility", "online");
CREATE INDEX "agents_last_heartbeat_idx" ON "agents"("last_heartbeat");
CREATE TABLE "new_trace_events" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "trace_id" TEXT NOT NULL,
    "task_id" TEXT NOT NULL,
    "parent_task_id" TEXT,
    "depth" INTEGER NOT NULL DEFAULT 0,
    "agent_name" TEXT NOT NULL DEFAULT '',
    "type" TEXT NOT NULL,
    "text" TEXT NOT NULL DEFAULT '',
    "data" TEXT NOT NULL DEFAULT '{}',
    "timestamp" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO "new_trace_events" ("agent_name", "data", "depth", "id", "parent_task_id", "task_id", "text", "timestamp", "trace_id", "type") SELECT "agent_name", "data", "depth", "id", "parent_task_id", "task_id", "text", "timestamp", "trace_id", "type" FROM "trace_events";
DROP TABLE "trace_events";
ALTER TABLE "new_trace_events" RENAME TO "trace_events";
CREATE INDEX "trace_events_trace_id_idx" ON "trace_events"("trace_id");
CREATE INDEX "trace_events_trace_id_timestamp_idx" ON "trace_events"("trace_id", "timestamp");
CREATE TABLE "new_trace_index" (
    "trace_id" TEXT NOT NULL PRIMARY KEY,
    "first_event_at" DATETIME NOT NULL,
    "last_event_at" DATETIME NOT NULL,
    "event_count" INTEGER NOT NULL DEFAULT 1,
    "updated_at" DATETIME NOT NULL
);
INSERT INTO "new_trace_index" ("event_count", "first_event_at", "last_event_at", "trace_id", "updated_at") SELECT "event_count", "first_event_at", "last_event_at", "trace_id", "updated_at" FROM "trace_index";
DROP TABLE "trace_index";
ALTER TABLE "new_trace_index" RENAME TO "trace_index";
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
