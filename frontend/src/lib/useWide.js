// Is there room to lay something out sideways?
//
// One answer, shared. Two components asking the same question at two different
// breakpoints is how a page ends up with a table that thinks it is on a phone
// sitting under a header that thinks it is on a laptop.
//
// It lived in the admin console's `DataTable` first, which is where the
// question came up; it moved here when the application process flow needed the
// same answer, because a component on the creator's dashboard importing a hook
// out of the console kit is a dependency in the wrong direction.
import { useEffect, useState } from "react";

/** Where sideways layouts start. Tailwind's `md`, read once and shared. */
export const WIDE_QUERY = "(min-width: 768px)";

/**
 * True where there is room.
 *
 * **Read synchronously rather than defaulted**, so neither form renders for a
 * frame before being replaced — a component that swaps shape on mount is a
 * layout shift, and only one of the two is ever in the DOM.
 */
export default function useWide() {
    const [wide, setWide] = useState(() =>
        typeof window === "undefined" ? true : window.matchMedia(WIDE_QUERY).matches,
    );
    useEffect(() => {
        const mq = window.matchMedia(WIDE_QUERY);
        const on = () => setWide(mq.matches);
        mq.addEventListener("change", on);
        return () => mq.removeEventListener("change", on);
    }, []);
    return wide;
}
