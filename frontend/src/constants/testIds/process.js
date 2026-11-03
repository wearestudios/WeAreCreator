// The homepage's "How it works": the process spine, its switch, the
// before/after strip and the feature row.

export const PROCESS = {
	section: 'process-section',
	switch: 'process-switch',
	tab: (key) => `process-tab-${key}`,
	steps: 'process-steps',
	// Numbered from 1, the way the nodes read.
	step: (n) => `process-step-${n}`,
	node: (n) => `process-node-${n}`,
	card: (n) => `process-card-${n}`,
	spine: 'process-spine',
	spineFill: 'process-spine-fill',
	kpi: (i) => `process-kpi-${i}`,
	beforeAfter: 'process-before-after',
	stripCta: 'process-strip-cta',
	featureRow: 'process-feature-row',
	feature: (key) => `process-feature-${key}`,
	featurePrev: 'process-feature-prev',
	featureNext: 'process-feature-next',
};
