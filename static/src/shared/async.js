export function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

// A poll loop that can never run forever, even if the server stops answering.
export function deadline(ms) {
    const expiresAt = Date.now() + ms;
    return { expired: () => Date.now() > expiresAt };
}
