/** The four session populations, in the order they are shown. Only "human" would be a study of people. */
export const POPS = [
  { id: "model", label: "Model pilot", title: "Language-model participants: a pilot, not people" },
  { id: "simulated-planted", label: "Simulated: planted", title: "Simulated participants with planted effects (dry run)" },
  { id: "simulated-no_effect", label: "Simulated: no effect", title: "Simulated participants with no effect (dry run)" },
  { id: "human", label: "Human", title: "Human participants (pending)" },
] as const;

export type PopId = (typeof POPS)[number]["id"];

export const POP_NOTE: Record<PopId, string> = {
  model:
    "Model participants are open-weights language models answering the same screens through the same API. They are a pilot of the pipeline and of how language models use AI advice; they are not people and say nothing about human decisions.",
  "simulated-planted":
    "Simulated participants follow a scripted behaviour model with effects planted on purpose. This dry run checks that the analysis recovers planted effects; it is not data.",
  "simulated-no_effect":
    "Simulated participants with no difference between arms. This dry run checks that the analysis does not find effects that are not there.",
  human: "No human sessions have been run. The study is ready to deploy; recruitment and ethics approval are pending.",
};

export const OUTCOME_LABEL: Record<string, string> = {
  accuracy: "Accuracy",
  cost: "Cost per decision",
  log_seconds: "Decision time (log seconds)",
  override: "Override of the AI",
  appropriate: "Appropriate reliance",
  brier: "Brier score of confidence",
  gap_loan: "Loan: error gap, under 25 vs 25 and over",
  gap_credit_limit: "Credit limit: error gap, female vs male",
  gap_marketing: "Marketing: error gap, under 60 vs 60 and over",
};

export const DOMAIN_LABEL: Record<string, string> = {
  loan: "Loan approval",
  marketing: "Marketing call",
  credit_limit: "Credit-limit review",
};
