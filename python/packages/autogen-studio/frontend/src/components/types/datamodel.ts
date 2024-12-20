export interface RequestUsage {
  prompt_tokens: number;
  completion_tokens: number;
}

export interface ImageContent {
  url: string;
  alt?: string;
  data?: string;
}

export interface FunctionCall {
  id: string;
  arguments: string; // JSON string
  name: string;
}

export interface FunctionExecutionResult {
  call_id: string;
  content: string;
}

// Base message configuration (maps to Python BaseMessage)
export interface BaseMessageConfig {
  source: string;
  models_usage?: RequestUsage;
}

// Message configurations (mapping directly to Python classes)
export interface TextMessageConfig extends BaseMessageConfig {
  content: string;
}

export interface MultiModalMessageConfig extends BaseMessageConfig {
  content: (string | ImageContent)[];
}

export interface StopMessageConfig extends BaseMessageConfig {
  content: string;
}

export interface HandoffMessageConfig extends BaseMessageConfig {
  content: string;
  target: string;
}

export interface ToolCallMessageConfig extends BaseMessageConfig {
  content: FunctionCall[];
}

export interface ToolCallResultMessageConfig extends BaseMessageConfig {
  content: FunctionExecutionResult[];
}

// Message type unions (matching Python type aliases)
export type InnerMessageConfig =
  | ToolCallMessageConfig
  | ToolCallResultMessageConfig;

export type ChatMessageConfig =
  | TextMessageConfig
  | MultiModalMessageConfig
  | StopMessageConfig
  | HandoffMessageConfig;

export type AgentMessageConfig =
  | TextMessageConfig
  | MultiModalMessageConfig
  | StopMessageConfig
  | HandoffMessageConfig
  | ToolCallMessageConfig
  | ToolCallResultMessageConfig;

// Database model
export interface DBModel {
  id?: number;
  user_id?: string;
  created_at?: string;
  updated_at?: string;
  version?: number;
}

export interface Message extends DBModel {
  config: AgentMessageConfig;
  session_id: number;
  run_id: string;
}

export interface Session extends DBModel {
  name: string;
  team_id?: number;
}

export interface SessionRuns {
  runs: Run[];
}

export interface BaseConfig {
  component_type: string;
  version?: string;
}

export interface WebSocketMessage {
  type: "message" | "result" | "completion" | "input_request" | "error";
  data?: AgentMessageConfig | TaskResult;
  status?: RunStatus;
  error?: string;
  timestamp?: string;
}

export interface TaskResult {
  messages: AgentMessageConfig[];
  stop_reason?: string;
}

export type ModelTypes =
  | "OpenAIChatCompletionClient"
  | "AzureOpenAIChatCompletionClient";

export type AgentTypes =
  | "AssistantAgent"
  | "CodingAssistantAgent"
  | "UserProxyAgent"
  | "MultimodalWebSurfer"
  | "FileSurfer"
  | "MagenticOneCoderAgent";

export type ToolTypes = "PythonFunction";

export type TeamTypes =
  | "RoundRobinGroupChat"
  | "SelectorGroupChat"
  | "MagenticOneGroupChat";

// class ComponentType(str, Enum):
//     TEAM = "team"
//     AGENT = "agent"
//     MODEL = "model"
//     TOOL = "tool"
//     TERMINATION = "termination"
export type TerminationTypes =
  | "MaxMessageTermination"
  | "StopMessageTermination"
  | "TextMentionTermination"
  | "TimeoutTermination"
  | "CombinationTermination";

export type ComponentTypes =
  | "team"
  | "agent"
  | "model"
  | "tool"
  | "termination";

export type ComponentConfigTypes =
  | TeamConfigTypes
  | AgentConfig
  | ModelConfigTypes
  | ToolConfig
  | TerminationConfigTypes;

export interface BaseModelConfig extends BaseConfig {
  model: string;
  model_type: ModelTypes;
  api_key?: string;
  base_url?: string;
}

export interface AzureOpenAIModelConfig extends BaseModelConfig {
  model_type: "AzureOpenAIChatCompletionClient";
  azure_deployment: string;
  api_version: string;
  azure_endpoint: string;
  azure_ad_token_provider: string;
}

export interface OpenAIModelConfig extends BaseModelConfig {
  model_type: "OpenAIChatCompletionClient";
}

export type ModelConfigTypes = AzureOpenAIModelConfig | OpenAIModelConfig;

export interface ToolConfig extends BaseConfig {
  name: string;
  description: string;
  content: string;
  tool_type: ToolTypes;
}
export interface AgentConfig extends BaseConfig {
  name: string;
  agent_type: AgentTypes;
  system_message?: string;
  model_client?: ModelConfigTypes;
  tools?: ToolConfig[];
  description?: string;
}
// export interface TerminationConfig extends BaseConfig {
//   termination_type: TerminationTypes;
//   max_messages?: number;
//   text?: string;
// }

export interface BaseTerminationConfig extends BaseConfig {
  termination_type: TerminationTypes;
}

export interface MaxMessageTerminationConfig extends BaseTerminationConfig {
  termination_type: "MaxMessageTermination";
  max_messages: number;
}

export interface TextMentionTerminationConfig extends BaseTerminationConfig {
  termination_type: "TextMentionTermination";
  text: string;
}

export interface CombinationTerminationConfig extends BaseTerminationConfig {
  termination_type: "CombinationTermination";
  operator: "and" | "or";
  conditions: TerminationConfigTypes[];
}

export type TerminationConfigTypes =
  | MaxMessageTerminationConfig
  | TextMentionTerminationConfig
  | CombinationTerminationConfig;

// export interface TeamConfig extends BaseConfig {
//   name: string;
//   participants: AgentConfig[];
//   team_type: TeamTypes;
//   model_client?: ModelConfig;
//   termination_condition?: TerminationConfig;
//   selector_prompt?: string;
// }

export interface BaseTeamConfig extends BaseConfig {
  name: string;
  participants: AgentConfig[];
  team_type: TeamTypes;
  termination_condition?: TerminationConfigTypes;
}

export interface RoundRobinGroupChatConfig extends BaseTeamConfig {
  team_type: "RoundRobinGroupChat";
}

export interface SelectorGroupChatConfig extends BaseTeamConfig {
  team_type: "SelectorGroupChat";
  selector_prompt: string;
  model_client: ModelConfigTypes;
}

export type TeamConfigTypes =
  | RoundRobinGroupChatConfig
  | SelectorGroupChatConfig;

export interface Team extends DBModel {
  config: TeamConfigTypes;
}

export interface TeamResult {
  task_result: TaskResult;
  usage: string;
  duration: number;
}

export interface Run {
  id: string;
  created_at: string;
  updated_at?: string;
  status: RunStatus;
  task: AgentMessageConfig;
  team_result: TeamResult | null;
  messages: Message[]; // Change to Message[]
  error_message?: string;
}

export type RunStatus =
  | "created"
  | "active" // covers 'streaming'
  | "awaiting_input"
  | "timeout"
  | "complete"
  | "error"
  | "stopped";
