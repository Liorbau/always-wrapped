export const POLL_MS = 1000;
export const FLASH_MS = 1200;
export const EVENT_STAGGER_MS = 280;
export const TRIGGER_COOLDOWN_MS = 4000;

export const EDGES = [
    ['node-dj', 'node-query_history'],
    ['node-dj', 'node-search_spotify'],
    ['node-dj', 'node-artist_top_tracks'],
    ['node-dj', 'node-get_audio_features'],
    ['node-dj', 'node-discover_new_tracks'],
    ['node-analyst', 'node-query_history'],
    ['node-wrapped', 'node-query_history'],
    ['node-evaluator', 'node-query_history'],
    ['node-evaluator', 'node-dj', 'dashed'],       // soft biases feed the DJ
    ['node-planner', 'node-calendar'],             // reads tomorrow's blocks
    ['node-planner', 'node-dj', 'dashed'],         // delegates each brief to the DJ
];

// Mirrors the step labels the server sends in `active.doing`.
export const TOOL_NODE_BY_ACTIVITY = {
    'exploring your history': 'node-query_history',
    'searching Spotify': 'node-search_spotify',
    'collecting candidate tracks': 'node-artist_top_tracks',
    'checking the mood': 'node-get_audio_features',
    'hunting new music': 'node-discover_new_tracks',
};

export const NODE_BY_AGENT = {
    wrapped: 'node-wrapped',
    evaluator: 'node-evaluator',
    dj: 'node-dj',
    analyst: 'node-analyst',
    planner: 'node-planner',
};
