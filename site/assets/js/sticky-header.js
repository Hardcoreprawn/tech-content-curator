/**
 * Sticky Header with Fade Title Effect
 * Detects when the first-entry title scrolls out of view and toggles
 * the header logo text visibility accordingly.
 * 
 * Uses Intersection Observer for efficient scroll detection
 */

(function() {
    // Get the h1 in first-entry and header element
    const firstEntryTitle = document.querySelector('.first-entry .entry-header h1');
    const header = document.querySelector('.header');

    // Only initialize if both elements exist
    if (!firstEntryTitle || !header) return;

    // Use Intersection Observer to detect when first-entry title is visible
    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) {
                    // Title has scrolled out of view - show header logo text
                    header.classList.add('scrolled');
                    firstEntryTitle.classList.add('hidden');
                } else {
                    // Title is visible - hide header logo text
                    header.classList.remove('scrolled');
                    firstEntryTitle.classList.remove('hidden');
                }
            });
        },
        {
            threshold: 0, // Trigger when any part leaves viewport
            rootMargin: '0px',
        }
    );

    // Start observing the first-entry title
    observer.observe(firstEntryTitle);

    // Optional: Clean up on page unload (good practice)
    window.addEventListener('beforeunload', () => {
        observer.disconnect();
    });
})();
