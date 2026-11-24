/** Shared types for OS1 surfaces, orchestrator state bus, cards, approvals, memory, and computers. */

export type Phase =
  | "preflight"
  | "boot"
  | "operator_welcome"
  | "operator_q1"
  | "operator_q1_hesitance"
  | "operator_q2"
  | "operator_q3"
  | "initiating"
  | "naming"
  | "samantha_first_meeting"
  | "active"
  | "asleep";

export type AgentState = "initializing" | "idle" | "listening" | "thinking" | "speaking";

export type ActiveSurface =
  | "conversation"
  | "home"
  | "inbox_cascade"
  | "your_computer"
  | "her_computer"
  | "swarm"
  | "made_just_now"
  | "connectors"
  | "voice_picker"
  | "memory";

export type Surface = "startup" | "preflight" | "boot" | "setup" | "waking" | "naming" | ActiveSurface;

export interface WorkItem {
  id: string;
  label: string;
  status: "running" | "waiting" | "done" | "cancelled" | "failed" | string;
  progress?: number;
  stage?: string;
  result?: string;
  logs?: string[];
  created_at?: number;
  updated_at?: number;
}

export interface MoodState {
  warmth: number;
  pace: number;
  overwhelm: number;
  compactMode: boolean;
}

export interface SpeakableAction {
  label: string;
  speakablePhrase: string;
  actionId?: string;
  tone?: "primary" | "secondary" | "danger";
}

export type Os1Card =
  | {
      kind: "ComparisonCard";
      id: string;
      title: string;
      subtitle?: string;
      options: { title: string; subtitle?: string; highlights?: string[]; meta?: string; speakablePhrase: string }[];
    }
  | {
      kind: "ChoicePairCard";
      id: string;
      prompt: string;
      left: { title: string; detail?: string; speakablePhrase: string };
      right: { title: string; detail?: string; speakablePhrase: string };
    }
  | {
      kind: "QuickDecisionCard";
      id: string;
      eyebrow?: string;
      title: string;
      body?: string;
      actions: SpeakableAction[];
    }
  | {
      kind: "ReadbackConfirmCard";
      id: string;
      stakes: "shared" | "money" | "forget" | "computer";
      title: string;
      summaryLines: string[];
      confirmAction: SpeakableAction;
      cancelAction: SpeakableAction;
    }
  | {
      kind: "DraftPreviewCard";
      id: string;
      recipient: string;
      subject?: string;
      body: string;
      actions: SpeakableAction[];
    }
  | {
      kind: "TimelineCard";
      id: string;
      title: string;
      steps: { time: string; title: string; detail?: string; status?: "done" | "now" | "next" }[];
      actions?: SpeakableAction[];
    }
  | {
      kind: "AudioSketchCard";
      id: string;
      title: string;
      mood?: string;
      duration?: string;
      bars?: number[];
      actions: SpeakableAction[];
    };

export type AudioSketchCard = Extract<Os1Card, { kind: "AudioSketchCard" }>;

export interface CanvasState {
  title: string;
  subtitle?: string;
  cards: Os1Card[];
  createdAt?: number;
}

export interface PendingAction {
  id: string;
  source: "hermes" | "cua" | "triage" | "memory" | "inbox" | "composio" | string;
  title: string;
  summaryLines: string[];
  stakes: "low" | "shared" | "money" | "forget" | "computer";
  options: { phrase: string; choice: string }[];
  runId?: string | null;
  requestId?: string | null;
  allowRememberRule?: boolean;
  createdAt?: number;
}

export interface UndoToast {
  id: string;
  label: string;
  expiresAt: number;
}

export interface RememberedShimmer {
  id: string;
  category: string;
  summary: string;
  at: number;
}

export type MemoryCategory = "people" | "places" | "things_you_love" | "things_that_hurt" | "promises";

export interface MemoryItem {
  id: string;
  category: MemoryCategory;
  summary: string;
  detail: string;
  source: string;
  created_at: number;
}

export type ConnectorPolicy = "full_access" | "ask_before_write" | "read_only" | "ask_every_time";

export interface ConnectorItem {
  slug: string;
  label: string;
  policy: ConnectorPolicy;
  connected: boolean;
  account_label: string;
  spoken_status: string;
  updated_at?: number;
}

export interface InboxItem {
  id: string;
  number: number;
  sender: string;
  subject: string;
  snippet: string;
  received_at: string;
  keeper_score: number;
  is_vip: boolean;
  category: string;
  status: string;
}

export interface ActivityItem {
  id: string;
  source: string;
  title: string;
  detail: string;
  status: string;
  created_at: number;
}

export interface VoiceSettings {
  voiceKey: string;
  speed: number;
  temperature: number;
  styleNote: string;
}

export interface CuaManifest {
  version: string;
  mode: string;
  allowedApps: string[];
  allowedPaths: string[];
  blockedApps: string[];
  telemetryEnabled: boolean;
}

export interface CuaState {
  connected: boolean;
  status: string;
  manifest: CuaManifest;
  recentActivity: ActivityItem[];
}

export interface HerComputerState {
  online: boolean;
  resolution: string;
  recentActivity: ActivityItem[];
}

export interface Os1BusState {
  connected: boolean;
  activeSurface: ActiveSurface;
  mood: MoodState;
  runs: WorkItem[];
  canvas: CanvasState | null;
  pendingAction: PendingAction | null;
  undoToast: UndoToast | null;
  rememberedShimmer: RememberedShimmer | null;
  memories: MemoryItem[];
  connectors: ConnectorItem[];
  inbox: InboxItem[];
  voice: VoiceSettings;
  cua: CuaState;
  herComputer: HerComputerState;
  visiblePhrases: string[];
}

export interface Os1State {
  connection: "idle" | "connecting" | "connected" | "error";
  error?: string;
  phase: Phase;
  agentState: AgentState;
  chips: string[];
  work: WorkItem[];
  voice: string;
  agentName?: string;
  agentLine: string;
  userLine: string;
  speechWarning?: string;
  installerStatus?: string;
  installerPercent?: number;
  installerMessage?: string;
  installerComponent?: string;
  installerComponentLabel?: string;
  installerReady?: boolean;
  storageDir?: string;
}

export interface Os1Config {
  orchestratorUrl: string;
  clientToken?: string;
}
