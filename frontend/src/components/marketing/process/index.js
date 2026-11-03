// Which mockup draws which step, by the `kind` its card carries in
// `HOME.processSpine` — so a step's copy and its drawing live together in
// the content module and the components stay presentational.
import StepCardApplied from "./StepCardApplied";
import StepCardApprove from "./StepCardApprove";
import StepCardBooked from "./StepCardBooked";
import StepCardBrief from "./StepCardBrief";
import StepCardCalendar from "./StepCardCalendar";
import StepCardCampaigns from "./StepCardCampaigns";
import StepCardKpis from "./StepCardKpis";
import StepCardPayout from "./StepCardPayout";
import StepCardShortlist from "./StepCardShortlist";
import StepCardSubmit from "./StepCardSubmit";

export const STEP_CARDS = {
    brief: StepCardBrief,
    shortlist: StepCardShortlist,
    calendar: StepCardCalendar,
    approve: StepCardApprove,
    kpis: StepCardKpis,
    campaigns: StepCardCampaigns,
    applied: StepCardApplied,
    booked: StepCardBooked,
    submit: StepCardSubmit,
    payout: StepCardPayout,
};
