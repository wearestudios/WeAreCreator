// Loading a surface only when somebody opens it.
//
// The whole app shipped as one file: every creator on mobile data downloaded
// the admin console, the brand console and the manager screens — three
// surfaces they will never see — before their own dashboard could paint. The
// audience is a mid-range Android phone on Indian mobile data, which is the
// case where that cost is not theoretical.
//
// `React.lazy` is the mechanism and this module is the two things it does not
// give you.

/**
 * **`React.lazy` does not retry.** The promise a lazy component is built from
 * is memoised *including its rejection*, so a chunk that failed to arrive
 * fails forever: remounting the boundary re-throws the same error and never
 * re-requests the file. That makes an ordinary "Try again" button a lie.
 *
 * So the retry happens here, inside the importer, where a fresh request really
 * is made — once, after a short pause, which is the shape of a chunk that lost
 * a race with a lift or a tunnel. If the second attempt fails too, the error is
 * tagged so the route boundary can say what actually went wrong and offer the
 * one thing that reliably fixes the other cause: a reload, which fetches a
 * fresh `index.html` and therefore the *current* chunk names. After a deploy
 * the old hashed file is genuinely gone, and no amount of retrying that URL
 * will bring it back.
 */
export function retryImport(importer, { delayMs = 400 } = {}) {
    return importer().catch(
        () =>
            new Promise((resolve, reject) => {
                setTimeout(() => {
                    importer().then(resolve, (error) => {
                        reject(asChunkError(error));
                    });
                }, delayMs);
            }),
    );
}

/**
 * Mark an import failure as one, so the boundary can tell it from a render
 * crash.
 *
 * **Tagged rather than matched on the message.** Webpack's own
 * `ChunkLoadError` is recognised too — it can be raised by a prefetch this
 * module never wrapped — but a copy edit to a browser's error string must not
 * be what decides which fallback somebody sees.
 */
export function asChunkError(error) {
    const wrapped = error instanceof Error ? error : new Error(String(error));
    wrapped.isChunkError = true;
    return wrapped;
}

/** Whether an error is a chunk that did not arrive, however it was raised. */
export function isChunkError(error) {
    if (!error) return false;
    return (
        error.isChunkError === true ||
        error.name === "ChunkLoadError" ||
        // Native ESM, which some browsers report rather than webpack's own.
        /Failed to fetch dynamically imported module|error loading dynamically imported module/i.test(
            error.message || "",
        )
    );
}
