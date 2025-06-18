from flask import Flask, request, render_template, session, redirect, url_for  # type: ignore
import requests  # type: ignore
import difflib
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'replace_with_your_secret_key'  # Change this to a secure key

class QuranTextChecker:
    def __init__(self):
        self.current_surah = None
        self.errors = []
    
    def get_surah_list(self):
        """Get list of all surahs"""
        try:
            url = "https://api.alquran.cloud/v1/surah"
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()['data']
        except Exception as e:
            print(f"Error fetching surah list: {e}")
        return []
    
    def get_surah_text(self, surah_number):
        """Get text of specific surah"""
        try:
            url = f"https://api.alquran.cloud/v1/surah/{surah_number}"
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()['data']
        except Exception as e:
            print(f"Error fetching surah {surah_number}: {e}")
        return None
    
    def normalize_arabic_text(self, text):
        """Normalize Arabic text for comparison"""
        # Remove diacritics (tashkeel)
        arabic_diacritics = re.compile(r'[\u064B-\u0652\u0670\u0640]')
        text = arabic_diacritics.sub('', text)
        
        # Remove extra spaces and normalize
        text = ' '.join(text.split())
        
        # Replace similar characters
        text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
        text = text.replace('ة', 'ه')
        text = text.replace('ى', 'ي')
        
        return text.strip()
    
    def compare_texts(self, spoken, original):
        """Compare spoken text with original Quran text"""
        spoken_normalized = self.normalize_arabic_text(spoken)
        original_normalized = self.normalize_arabic_text(original)
        
        # Calculate similarity percentage
        similarity = difflib.SequenceMatcher(None, spoken_normalized, original_normalized).ratio()
        
        # Use difflib to find differences
        matcher = difflib.SequenceMatcher(None, spoken_normalized.split(), original_normalized.split())
        differences = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                differences.append({
                    'type': 'incorrect',
                    'spoken': ' '.join(spoken_normalized.split()[i1:i2]),
                    'correct': ' '.join(original_normalized.split()[j1:j2]),
                    'position': i1
                })
            elif tag == 'delete':
                differences.append({
                    'type': 'missing',
                    'missing': ' '.join(original_normalized.split()[j1:j2]),
                    'position': i1
                })
            elif tag == 'insert':
                differences.append({
                    'type': 'extra',
                    'extra': ' '.join(spoken_normalized.split()[i1:i2]),
                    'position': i1
                })
        
        return differences, similarity

# Create a global instance of the checker for convenience
qtc = QuranTextChecker()

@app.route('/')
def index():
    surahs = qtc.get_surah_list()
    return render_template('index.html', surahs=surahs)

@app.route('/start', methods=['POST'])
def start():
    surah_number = request.form.get('surah_number')
    try:
        surah_number = int(surah_number)
    except Exception as e:
        return redirect(url_for('index'))
    
    surah_data = qtc.get_surah_text(surah_number)
    if not surah_data:
        return "❌ Could not load surah data. Please check your internet connection."
    
    # Initialize session variables (we won’t handle per-ayah inputs here)
    session['surah'] = surah_data       # surah data from API (a dictionary)
    session['errors'] = []              # collect error details (list)
    session['total_similarity'] = 0.0   # cumulative similarity score
    session['verses_attempted'] = 0     # count attempted comparisons
    
    return redirect(url_for('recite'))

@app.route('/recite', methods=['GET', 'POST'])
def recite():
    if 'surah' not in session:
        return redirect(url_for('index'))
    
    surah = session['surah']
    ayahs = surah.get('ayahs', [])
    
    # Generate one combined text string from all ayahs
    full_text = ""
    # If surah is Al-Fatiha (surah number 1), display the first ayah (Bismillah) on its own line.
    if surah['number'] == 1 and len(ayahs) > 0:
        full_text += ayahs[0]['text'] + "\n"  # The Bismillah
        # Then append the remaining ayahs with numbering starting from 1.
        for idx, ayah in enumerate(ayahs[1:], start=1):
            full_text += ayah['text'] + f"({idx}) "
    else:
        for idx, ayah in enumerate(ayahs, start=1):
            full_text += ayah['text'] + f"({idx}) "
    
    if request.method == 'POST':
        # Get the full recitation input
        user_input = request.form.get('user_input', '').strip()
        if user_input:
            differences, similarity = qtc.compare_texts(user_input, full_text)
            session['total_similarity'] = similarity
            session['verses_attempted'] = 1  # One big comparison for the full surah.
            session['errors'] = []
            if differences:
                for diff in differences:
                    error_info = {
                        'error': diff,
                        'similarity': similarity,
                        'timestamp': datetime.now().strftime("%H:%M:%S")
                    }
                    session['errors'].append(error_info)
            return redirect(url_for('report'))
        else:
            error_message = "⚠️ Empty input, please provide your recitation."
            return render_template('recite.html', surah=surah, full_text=full_text, error_message=error_message)
    
    return render_template('recite.html', surah=surah, full_text=full_text)

@app.route('/report')
def report():
    if 'surah' not in session:
        return redirect(url_for('index'))
        
    errors = session.get('errors', [])
    total_similarity = session.get('total_similarity', 0.0)
    verses_attempted = session.get('verses_attempted', 0)
    avg_similarity = (total_similarity / verses_attempted * 100) if verses_attempted > 0 else 0
    error_rate = (len(errors) / verses_attempted * 100) if verses_attempted > 0 else 0
    
    return render_template('report.html',
                           errors=errors,
                           verses_attempted=verses_attempted,
                           total_errors=len(errors),
                           avg_similarity=round(avg_similarity, 1),
                           error_rate=round(error_rate, 1))

if __name__ == "__main__":
    app.run(debug=True)
