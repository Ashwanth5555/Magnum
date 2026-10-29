/** Plain-English rendering of the policy's refusal codes, shared by every
  * screen that has to explain why nothing was sent. */
export const SUPPRESSION_COPY: Record<string, string> = {
  FREQUENCY_CAPPED: 'Contact cap reached — one push a day, three a week.',
  POST_PURCHASE_SUPPRESS: 'Ordered in the last 12 hours. Nothing to nudge.',
  NO_MARKETING_CONSENT: 'No marketing consent on file.',
  OFFER_MARGIN_NEGATIVE: 'Every candidate loses money at its measured lift.',
  OFFER_UPLIFT_BELOW_THRESHOLD: 'No candidate clears the 2 pp lift bar.',
}
