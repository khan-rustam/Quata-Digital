// Recruitment pipeline stages for applicants (HRMS slice 1B).
// Backward-compatible: the original new/shortlisted/interviewed/rejected/hired
// values still render. The email-sending transitions (shortlisted, hired,
// rejected) go through their dedicated dialogs; the rest are plain stage moves.

export type ApplicantStage =
  | "new"
  | "hr_review"
  | "shortlisted"
  | "interview_scheduled"
  | "interviewed"
  | "assessment"
  | "reference_check"
  | "offer"
  | "offer_accepted"
  | "hired"
  | "rejected"
  | "archived";

export type StageVariant = "default" | "warn" | "success" | "danger" | "brand";

export const STAGE_LABEL: Record<string, string> = {
  new: "New",
  hr_review: "HR review",
  shortlisted: "Shortlisted",
  interview_scheduled: "Interview scheduled",
  interviewed: "Interview completed",
  assessment: "Assessment",
  reference_check: "Reference check",
  offer: "Offer generated",
  offer_accepted: "Offer accepted",
  hired: "Hired",
  rejected: "Rejected",
  archived: "Archived",
};

export const STAGE_VARIANT: Record<string, StageVariant> = {
  new: "default",
  hr_review: "default",
  shortlisted: "brand",
  interview_scheduled: "warn",
  interviewed: "warn",
  assessment: "warn",
  reference_check: "warn",
  offer: "brand",
  offer_accepted: "success",
  hired: "success",
  rejected: "danger",
  archived: "default",
};

export function stageLabel(status: string): string {
  return STAGE_LABEL[status] ?? status;
}

export function stageVariant(status: string): StageVariant {
  return STAGE_VARIANT[status] ?? "default";
}

// Stages the admin sets directly (no automated email). shortlisted / hired /
// rejected are intentionally excluded — they run through their email dialogs.
export const PLAIN_STAGES: { value: ApplicantStage; label: string }[] = [
  { value: "new", label: "New" },
  { value: "hr_review", label: "HR review" },
  { value: "interview_scheduled", label: "Interview scheduled" },
  { value: "interviewed", label: "Interview completed" },
  { value: "assessment", label: "Assessment" },
  { value: "reference_check", label: "Reference check" },
  { value: "offer", label: "Offer generated" },
  { value: "offer_accepted", label: "Offer accepted" },
  { value: "archived", label: "Archived" },
];
