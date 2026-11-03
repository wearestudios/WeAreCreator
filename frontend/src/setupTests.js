// Jest setup for component tests (CRA picks this file up by name).
//
// CRA's jsdom environment has no TextEncoder, and react-router v7 reads it
// at import time. Node has had both since v11.
import { TextDecoder, TextEncoder } from "util";

if (typeof globalThis.TextEncoder === "undefined") {
    globalThis.TextEncoder = TextEncoder;
    globalThis.TextDecoder = TextDecoder;
}
