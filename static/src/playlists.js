import * as playlists from './features/playlists/state.js';
import { initPageNav } from './shared/pageNav.js';

initPageNav([{ selector: '#pl-back', direction: 'back' }]);
playlists.init();
