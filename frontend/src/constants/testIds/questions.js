// Test IDs for campaign question threads — the creator↔team channel that is
// deliberately not the internal work notes.

export const QUESTIONS = {
	section: 'campaign-questions',
	list: 'campaign-questions-list',
	message: (id) => `campaign-question-${id}`,
	input: 'campaign-questions-input',
	send: 'campaign-questions-send',
	empty: 'campaign-questions-empty',
	// The staff side.
	thread: (creatorId) => `question-thread-${creatorId}`,
	replyInput: 'question-reply-input',
	replySend: 'question-reply-send',
	threadsPanel: 'question-threads-panel',
	queueRow: (cid, creatorId) => `queue-question-${cid}-${creatorId}`,
};
