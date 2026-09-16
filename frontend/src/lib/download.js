/**
 * Fetching a generated file, as the signed-in person.
 *
 * **Through `api`, never a bare `href` at the backend** — the lesson
 * `BrandDocuments` and the brand's close-out export already learned. The
 * session cookie is `SameSite=None`, so an anchor pointing at the API origin
 * rides along in production and silently does not on a plain-http laptop,
 * which is the worst kind of difference: it works where it is hard to test and
 * fails where it is easy to blame on something else.
 *
 * It also means a refusal arrives as a `Blob` rather than as a JSON body, so
 * the bytes have to be read back before the message can be formatted —
 * otherwise a 403 downloads as a file called `analytics.csv` containing the
 * word "Forbidden".
 */
import { api } from "@/lib/api";

export async function downloadCsv(path, filename) {
    let data;
    try {
        ({ data } = await api.get(path, { responseType: "blob" }));
    } catch (err) {
        const blob = err?.response?.data;
        if (blob instanceof Blob) {
            // Re-hydrate the refusal so `notifyError` has something to say.
            const text = await blob.text();
            try {
                err.response.data = JSON.parse(text);
            } catch {
                err.response.data = { detail: text };
            }
        }
        throw err;
    }

    const url = URL.createObjectURL(data);
    try {
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
    } finally {
        // Released on the next tick rather than immediately: revoking before
        // the click has been handled cancels the download in some browsers.
        setTimeout(() => URL.revokeObjectURL(url), 0);
    }
}
