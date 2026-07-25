// Dashboard boot. The only place features are wired to each other.

import * as backdrop from './features/backdrop/ribbons.js';
import * as chat from './features/chat/state.js';
import * as insight from './features/insight/state.js';
import * as library from './features/library/state.js';
import * as search from './features/search/state.js';
import * as wrappedMenu from './features/wrapped/menu.js';
import * as wrapped from './features/wrapped/state.js';

backdrop.init();
library.init();
insight.init();
search.init();
wrapped.init();
wrappedMenu.init({ onOpen: wrapped.open });
chat.init({ onWrappedRequest: wrapped.open });
