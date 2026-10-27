export type BlockedEvidenceMatch = {
  topic: string;
  reason: string;
  url: string;
  title: string;
};
export type EvidenceRequestNotice = {
  id: string;
  requestedAt: string;
  blocked: BlockedEvidenceMatch[];
  dismissedAt?: string;
};
