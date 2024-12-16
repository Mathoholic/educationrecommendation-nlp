document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.getElementById('searchForm');
    const resultsContainer = document.getElementById('resultsContainer');
    
    searchForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const query = this.querySelector('input[name="query"]').value;
        const loadingHtml = '<div class="loading">Searching...</div>';
        resultsContainer.innerHTML = loadingHtml;
        
        try {
            const response = await fetch('/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `query=${encodeURIComponent(query)}`
            });
            
            const data = await response.json();
            
            if (data.results?.length) {
                resultsContainer.innerHTML = data.results.map(program => `
                    <div class="program-card">
                        <div class="similarity-badge">${(program.similarity_score * 100).toFixed(2)}% Match</div>
                        <h3>${program.program_name}</h3>
                        <p><strong>Institution:</strong> ${program.institution_name}</p>
                        <p><strong>Location:</strong> ${program.campus_location}</p>
                        <p><strong>Discipline:</strong> ${program.discipline}</p>
                    </div>
                `).join('');
            } else {
                resultsContainer.innerHTML = '<p>No results found</p>';
            }
        } catch (error) {
            resultsContainer.innerHTML = '<p>Error searching programs</p>';
            console.error('Search error:', error);
        }
    });
});