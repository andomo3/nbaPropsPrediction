import { useEffect, useState } from 'react';

/**
 * Minimal JSON fetch hook. Returns { data, loading, error } and ignores
 * responses that arrive after the URL has changed.
 *
 * Pass a falsy url to stay idle.
 */
export default function useFetch(url) {
    const [state, setState] = useState({ data: null, loading: Boolean(url), error: null });

    useEffect(() => {
        if (!url) {
            setState({ data: null, loading: false, error: null });
            return undefined;
        }

        let cancelled = false;
        setState({ data: null, loading: true, error: null });

        fetch(url)
            .then((res) => {
                const ct = res.headers.get('content-type') || '';
                if (!ct.includes('application/json')) {
                    throw new Error(`Server error (HTTP ${res.status})`);
                }
                return res.json().then((json) => {
                    if (!res.ok) throw new Error(json.detail || `Request failed (HTTP ${res.status})`);
                    return json;
                });
            })
            .then((data) => !cancelled && setState({ data, loading: false, error: null }))
            .catch((err) => !cancelled && setState({ data: null, loading: false, error: err.message }));

        return () => { cancelled = true; };
    }, [url]);

    return state;
}
