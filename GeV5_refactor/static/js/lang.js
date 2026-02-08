function changeLanguage(language) {
    localStorage.setItem('language', language);
    location.reload(); // Reload the page to apply the new language
}

function loadLanguage() {
    const language = localStorage.getItem('language') || 'fr';
    fetch(`/static/lang/${language}.csv`)
        .then(response => response.text())
        .then(csvText => {
            const data = parseCSV(csvText);
            document.querySelectorAll('[data-translate-key]').forEach(element => {
                const key = element.getAttribute('data-translate-key');
                if (data[key]) {
                    let text = data[key];
                    // Replace placeholders with actual values
                    if (element.hasAttribute('data-echeance')) {
                        const echeance = element.getAttribute('data-echeance');
                        text = text.replace('{{ echeance }}', echeance);
                    }
                    element.innerText = text;
                }
            });
        })
        .catch(error => console.error('Error loading language file:', error));
}

function parseCSV(text) {
    const lines = text.split('\n');
    const result = {};
    for (let i = 1; i < lines.length; i++) {
        const [key, value] = lines[i].split(',');
        if (key && value) {
            result[key] = value.trim();
        }
    }
    return result;
}

document.addEventListener('DOMContentLoaded', loadLanguage);
