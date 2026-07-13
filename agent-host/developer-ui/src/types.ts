export type HostedAgent = {
  id: string;
  name: string;
  entry_file: string;
  status: string;
  port: number | null;
  pid: number | null;
  error_message: string | null;
  registry_online: boolean | null;
  env_keys: string[];
  created_at: string;
  updated_at: string;
};

export type EnvRow = {
  key: string;
  value: string;
};
