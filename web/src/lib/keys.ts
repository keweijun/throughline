/** The keys that send from any writing box on this computer, Enter aside: Ctrl+Enter, or ⌘ Enter on a Mac. */
export const sendKeys = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘ Enter' : 'Ctrl+Enter';
