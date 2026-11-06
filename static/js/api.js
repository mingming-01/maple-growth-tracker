/** Browser-side API transport and JSON response handling. */

export function apiFetch(url, options = {}) {
    return window.fetch(url, options);
}

export async function readApiResponse(response, fallbackMessage) {
    let data = {};
    try {
        data = await response.json();
    } catch (error) {
        // Non-JSON responses use the caller's safe fallback message.
    }
    if (!response.ok) {
        throw new Error(data.error || fallbackMessage);
    }
    return data;
}
