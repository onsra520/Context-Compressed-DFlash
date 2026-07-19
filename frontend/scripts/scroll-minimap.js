document.addEventListener('DOMContentLoaded', () => {
    const minimap = document.getElementById('minimap');
    if (!minimap) return;
    
    const markers = minimap.querySelectorAll('.minimap-marker');
    let closeTimeout = null;
    let activeMarker = null;

    // Hover logic
    markers.forEach(marker => {
        marker.addEventListener('pointerenter', () => {
            if (closeTimeout) {
                clearTimeout(closeTimeout);
                closeTimeout = null;
            }
            
            // Remove hover state from all other markers
            markers.forEach(m => {
                if (m !== marker) m.classList.remove('is-hovered');
            });
            
            marker.classList.add('is-hovered');
        });

        marker.addEventListener('pointerleave', () => {
            closeTimeout = setTimeout(() => {
                marker.classList.remove('is-hovered');
            }, 150); // 150ms delay
        });

        // Click to scroll
        marker.addEventListener('click', () => {
            const targetId = marker.getAttribute('data-target');
            const section = document.getElementById(targetId);
            if (section) {
                // Ensure smooth scroll applies unless prefers-reduced-motion is enabled
                const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                section.scrollIntoView({ behavior: prefersReduced ? 'auto' : 'smooth' });
                marker.classList.remove('is-hovered');
            }
        });
    });

    // Active Section Tracking via IntersectionObserver
    const observerOptions = {
        root: null,
        rootMargin: '-30% 0px -70% 0px', // Trigger closer to the top of the viewport
        threshold: 0
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.getAttribute('id');
                
                // Update markers
                markers.forEach(marker => {
                    if (marker.getAttribute('data-target') === id) {
                        marker.classList.add('active');
                    } else {
                        marker.classList.remove('active');
                    }
                });
            }
        });
    }, observerOptions);

    markers.forEach(marker => {
        const targetId = marker.getAttribute('data-target');
        const section = document.getElementById(targetId);
        if (section) {
            observer.observe(section);
        }
    });
});
