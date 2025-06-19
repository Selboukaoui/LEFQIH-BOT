from flask import Flask, request, render_template, session, redirect, url_for, jsonify
import requests
import difflib
import re
from datetime import datetime
import unicodedata

app = Flask(__name__)
app.secret_key = 'your_secure_secret_key_here_2025'  # Change this to a secure key

class QuranTextChecker:
    def __init__(self):
        self.current_surah = None
        self.errors = []
        # Enhanced Arabic character mappings for better text comparison
        self.arabic_normalizations = {
            # Hamza variations
            'ء': 'ء',  # Hamza
            'أ': 'ا',  # Alif with Hamza above
            'إ': 'ا',  # Alif with Hamza below
            'آ': 'ا',  # Alif with Madda
            'ٱ': 'ا',  # Alif Wasla (this is the key fix!)
            
            # Ya variations
            'ي': 'ي',  # Ya
            'ى': 'ي',  # Alif Maksura
            'ئ': 'ي',  # Ya with Hamza
            
            # Ta Marbuta variations
            'ة': 'ه',  # Ta Marbuta
            'ت': 'ت',  # Ta
            
            # Ha variations
            'ه': 'ه',  # Ha
            'ح': 'ح',  # Ha with dot
            
            # Other common variations
            'ک': 'ك',  # Farsi Kaf to Arabic Kaf
            'گ': 'ك',  # Farsi Gaf to Arabic Kaf
            'ی': 'ي',  # Farsi Ya to Arabic Ya
        }
    
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
        """
        Enhanced Arabic text normalization for Quranic text comparison
        """
        if not text:
            return ""
        
        # Step 1: Basic Unicode normalization
        text = unicodedata.normalize('NFKD', text)
        
        # Step 2: Remove all diacritical marks (tashkeel)
        # Keep only the base Arabic characters
        no_diacritics = ''.join(char for char in text if not unicodedata.combining(char))
        
        # Step 3: Apply character-level normalizations
        normalized_chars = []
        for char in no_diacritics:
            # Apply our custom Arabic normalizations
            normalized_char = self.arabic_normalizations.get(char, char)
            normalized_chars.append(normalized_char)
        
        normalized_text = ''.join(normalized_chars)
        
        # Step 4: Remove tatweel (kashida) characters
        normalized_text = normalized_text.replace("ـ", "")
        
        # Step 5: Remove verse numbers in parentheses (1), (2), etc.
        normalized_text = re.sub(r'\(\s*\d+\s*\)', '', normalized_text)
        
        # Step 6: Remove standalone digits
        normalized_text = re.sub(r'\d+', '', normalized_text)
        
        # Step 7: Clean up extra whitespace
        normalized_text = ' '.join(normalized_text.split())
        
        # Step 8: Final Unicode normalization
        return unicodedata.normalize('NFKC', normalized_text.strip())

    def advanced_word_comparison(self, word1, word2):
        """
        Advanced word comparison that handles common Arabic spelling variations
        """
        # Normalize both words
        norm_word1 = self.normalize_arabic_text(word1)
        norm_word2 = self.normalize_arabic_text(word2)
        
        # Direct match after normalization
        if norm_word1 == norm_word2:
            return True, 1.0
        
        # Calculate similarity ratio
        similarity = difflib.SequenceMatcher(None, norm_word1, norm_word2).ratio()
        
        # Consider words similar if they're very close (accounting for minor differences)
        similarity_threshold = 0.8
        is_similar = similarity >= similarity_threshold
        
        return is_similar, similarity

    def check_current_words(self, spoken, full_text, position):
        """Enhanced word checking with better Arabic comparison"""
        if not spoken or not full_text:
            return []
            
        spoken_normalized = self.normalize_arabic_text(spoken)
        spoken_words = [w for w in spoken_normalized.split() if w.strip()]
        
        # Get expected words from current position
        full_normalized = self.normalize_arabic_text(full_text)
        all_words = [w for w in full_normalized.split() if w.strip()]
        
        if position >= len(all_words):
            return []
        
        errors = []
        
        # Check each spoken word against expected words
        for i, spoken_word in enumerate(spoken_words):
            expected_position = position + i
            
            if expected_position < len(all_words):
                expected_word = all_words[expected_position]
                
                # Use advanced comparison
                is_similar, similarity = self.advanced_word_comparison(spoken_word, expected_word)
                
                if not is_similar:
                    errors.append({
                        'position': expected_position,
                        'spoken': spoken_word,
                        'expected': expected_word,
                        'type': 'incorrect',
                        'similarity': round(similarity * 100, 1),
                        'original_spoken': spoken_word,  # Keep original for display
                        'original_expected': expected_word
                    })
            else:
                # Extra words beyond the expected text
                errors.append({
                    'position': expected_position,
                    'spoken': spoken_word,
                    'expected': '',
                    'type': 'extra',
                    'similarity': 0,
                    'original_spoken': spoken_word
                })
        
        return errors

    def compare_texts(self, spoken, original):
        """Enhanced text comparison with better Arabic handling"""
        spoken_normalized = self.normalize_arabic_text(spoken)
        original_normalized = self.normalize_arabic_text(original)
        
        # Calculate overall similarity
        similarity = difflib.SequenceMatcher(None, spoken_normalized, original_normalized).ratio()
        
        # Word-level comparison with advanced matching
        spoken_words = spoken_normalized.split()
        original_words = original_normalized.split()
        
        # Use difflib to find the best alignment
        matcher = difflib.SequenceMatcher(None, spoken_words, original_words)
        differences = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                # Check each replacement individually for better accuracy
                spoken_part = spoken_words[i1:i2]
                correct_part = original_words[j1:j2]

                # Try to match words individually within the replacement
                for k, (s_word, c_word) in enumerate(zip(spoken_part, correct_part)):
                    is_similar, word_similarity = self.advanced_word_comparison(s_word, c_word)
                    if not is_similar:
                        differences.append({
                            'type': 'incorrect',
                            'spoken': s_word,
                            'correct': c_word,
                            'similarity': round(word_similarity * 100, 1)
                        })
                
                # Handle length differences
                if len(spoken_part) > len(correct_part):
                    for extra_word in spoken_part[len(correct_part):]:
                        differences.append({
                            'type': 'extra',
                            'extra': extra_word
                        })
                elif len(correct_part) > len(spoken_part):
                    for missing_word in correct_part[len(spoken_part):]:
                        differences.append({
                            'type': 'missing',
                            'missing': missing_word
                        })
                        
            elif tag == 'delete':
                missing_words = original_words[j1:j2]
                for missing_word in missing_words:
                    if missing_word.strip():
                        differences.append({
                            'type': 'missing',
                            'missing': missing_word
                        })
                        
            elif tag == 'insert':
                extra_words = spoken_words[i1:i2]
                for extra_word in extra_words:
                    if extra_word.strip():
                        differences.append({
                            'type': 'extra',
                            'extra': extra_word
                        })
        
        return differences, similarity

# Create a global instance of the checker for convenience.
qtc = QuranTextChecker()

def get_next_expected_words(full_text, position, num_words=5):
    """Get the next expected words from the given position"""
    if not full_text:
        return ""
    
    normalized_text = qtc.normalize_arabic_text(full_text)
    words = [w for w in normalized_text.split() if w.strip()]
    
    if position >= len(words):
        return "End of Surah"
    
    end_pos = min(position + num_words, len(words))
    return ' '.join(words[position:end_pos])

def generate_improvement_suggestions(differences):
    """Generate personalized improvement suggestions with Arabic-specific advice"""
    suggestions = []
    
    if not differences:
        return ["Perfect recitation! Excellent work! 🎉"]
    
    incorrect_count = len([d for d in differences if d.get('type') == 'incorrect'])
    missing_count = len([d for d in differences if d.get('type') == 'missing'])
    extra_count = len([d for d in differences if d.get('type') == 'extra'])
    
    # Analyze common Arabic mistakes
    hamza_errors = sum(1 for d in differences if d.get('type') == 'incorrect' and 
                      ('ا' in d.get('spoken', '') or 'ٱ' in d.get('correct', '')))
    
    if hamza_errors > 0:
        suggestions.append("🔤 Focus on Hamzat Al-Wasl (ٱ) vs regular Alif (ا) - this is common in Quranic Arabic")
    
    if incorrect_count > missing_count and incorrect_count > extra_count:
        suggestions.append("🎯 Focus on pronunciation accuracy - review the correct pronunciation of words")
        suggestions.append("📚 Practice with Tajweed rules for better accuracy")
        
    if missing_count > 0:
        suggestions.append("💭 Practice memorization - some verses were skipped or missed")
        suggestions.append("🔄 Try reciting slower to avoid missing words")
        
    if extra_count > 0:
        suggestions.append("⚡ Be careful not to add extra words during recitation")
        suggestions.append("🎧 Listen to professional recitations for better flow")
    
    # Add general Arabic-specific suggestions
    if incorrect_count > 0:
        suggestions.append("📖 Arabic text may contain special characters like Hamzat Al-Wasl (ٱ)")
        suggestions.append("🕌 Consider practicing with a Quran teacher for proper pronunciation")
    
    return suggestions

@app.route('/')
def index():
    surahs = qtc.get_surah_list()
    return render_template('index.html', surahs=surahs)

@app.route('/start', methods=['POST'])
def start():
    surah_number = request.form.get('surah_number')
    try:
        surah_number = int(surah_number)
    except (ValueError, TypeError):
        return redirect(url_for('index'))
    
    surah_data = qtc.get_surah_text(surah_number)
    if not surah_data:
        return "❌ Could not load surah data. Please check your internet connection."
    
    # Build the full text by concatenating all ayahs with their verse numbers.
    ayahs = surah_data.get('ayahs', [])
    full_text = ""
    
    if surah_data['number'] == 1 and len(ayahs) > 0:
        # For Al-Fatiha, handle Bismillah separately
        full_text += ayahs[0]['text'] + "\n"
        for idx, ayah in enumerate(ayahs[1:], start=1):
            full_text += ayah['text'] + f" ({idx}) "
    else:
        for idx, ayah in enumerate(ayahs, start=1):
            full_text += ayah['text'] + f" ({idx}) "
    
    # Initialize session variables.
    session['surah'] = surah_data
    session['full_text'] = full_text.strip()
    session['errors'] = []
    session['total_similarity'] = 0.0
    session['verses_attempted'] = 0
    session['current_position'] = 0
    
    return redirect(url_for('recite'))

@app.route('/start_realtime_session', methods=['POST'])
def start_realtime_session():
    """Initialize real-time session variables"""
    session['current_position'] = 0
    session['realtime_errors'] = []
    session['start_time'] = datetime.now().isoformat()
    
    if 'full_text' in session:
        # Count total words for progress tracking
        normalized_text = qtc.normalize_arabic_text(session['full_text'])
        session['total_words'] = len([w for w in normalized_text.split() if w.strip()])
    else:
        session['total_words'] = 0
    
    return jsonify({
        'status': 'initialized',
        'total_words': session.get('total_words', 0),
        'message': 'Enhanced Arabic text processing enabled'
    })

@app.route('/check_realtime', methods=['POST'])
def check_realtime():
    """Check spoken text in real-time against expected text with enhanced Arabic processing"""
    try:
        data = request.get_json()
        spoken_text = data.get('text', '').strip()
        
        if not spoken_text:
            return jsonify({'errors': [], 'current_position': session.get('current_position', 0)})
        
        current_position = session.get('current_position', 0)
        full_text = session.get('full_text', '')
        
        # Check if spoken text matches expected position in surah
        errors = qtc.check_current_words(spoken_text, full_text, current_position)
        
        # Update position based on spoken words (use normalized count)
        spoken_normalized = qtc.normalize_arabic_text(spoken_text)
        spoken_words_count = len([w for w in spoken_normalized.split() if w.strip()])
        new_position = current_position + spoken_words_count
        session['current_position'] = new_position
        
        # Store errors for later analysis
        if 'realtime_errors' not in session:
            session['realtime_errors'] = []
        
        if errors:
            session['realtime_errors'].extend(errors)
        
        # Get next expected words for suggestion
        suggestion = get_next_expected_words(full_text, new_position, 3)
        total_words = session.get('total_words', 1)
        progress_percentage = min((new_position / total_words) * 100, 100) if total_words > 0 else 0
        
        return jsonify({
            'errors': errors,
            'current_position': new_position,
            'suggestion': suggestion,
            'progress_percentage': round(progress_percentage, 1),
            'total_words': total_words,
            'debug_info': {
                'spoken_normalized': qtc.normalize_arabic_text(spoken_text),
                'words_processed': spoken_words_count
            }
        })
        
    except Exception as e:
        print(f"Error in check_realtime: {e}")
        return jsonify({'errors': [], 'current_position': session.get('current_position', 0), 'error': str(e)})

@app.route('/final_analysis', methods=['POST'])
def final_analysis():
    """Provide comprehensive analysis when user stops recording"""
    try:
        data = request.get_json()
        full_transcript = data.get('transcript', '').strip()
        surah_text = session.get('full_text', '')
        
        if not full_transcript or not surah_text:
            return jsonify({'error': 'No transcript or surah text available'})
        
        # Comprehensive analysis with enhanced Arabic processing
        differences, similarity = qtc.compare_texts(full_transcript, surah_text)
        
        # Calculate detailed metrics
        total_words = len([w for w in qtc.normalize_arabic_text(surah_text).split() if w.strip()])
        spoken_words = len([w for w in qtc.normalize_arabic_text(full_transcript).split() if w.strip()])
        
        # Categorize errors
        errors_by_type = {
            'incorrect': [d for d in differences if d.get('type') == 'incorrect'],
            'missing': [d for d in differences if d.get('type') == 'missing'],
            'extra': [d for d in differences if d.get('type') == 'extra']
        }
        
        # Calculate accuracy metrics
        total_errors = len(differences)
        accuracy_percentage = similarity * 100
        completion_percentage = min((spoken_words / total_words) * 100, 100) if total_words > 0 else 0
        
        # Generate enhanced suggestions
        suggestions = generate_improvement_suggestions(differences)
        
        # Detailed analysis object
        analysis = {
            'overall_accuracy': round(accuracy_percentage, 1),
            'completion_percentage': round(completion_percentage, 1),
            'total_words': total_words,
            'spoken_words': spoken_words,
            'total_errors': total_errors,
            'errors_by_type': errors_by_type,
            'error_counts': {
                'incorrect': len(errors_by_type['incorrect']),
                'missing': len(errors_by_type['missing']),
                'extra': len(errors_by_type['extra'])
            },
            'suggestions': suggestions,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'session_duration': calculate_session_duration(),
            'processing_info': {
                'enhanced_arabic_processing': True,
                'normalization_applied': True,
                'hamza_aware': True
            }
        }
        
        # Store analysis in session for potential report generation
        session['final_analysis'] = analysis
        session['final_transcript'] = full_transcript
        
        return jsonify(analysis)
        
    except Exception as e:
        print(f"Error in final_analysis: {e}")
        return jsonify({'error': f'Analysis failed: {str(e)}'})

def calculate_session_duration():
    """Calculate how long the session lasted"""
    start_time_str = session.get('start_time')
    if start_time_str:
        try:
            start_time = datetime.fromisoformat(start_time_str)
            duration = datetime.now() - start_time
            return f"{duration.seconds // 60}m {duration.seconds % 60}s"
        except:
            pass
    return "Unknown"

@app.route('/recite', methods=['GET', 'POST'])
def recite():
    if 'surah' not in session:
        return redirect(url_for('index'))
    
    surah = session['surah']
    full_text = session.get('full_text', '')
    
    if request.method == 'POST':
        # Handle traditional form submission (fallback)
        user_input = request.form.get('user_input', '').strip()
        if user_input:
            differences, similarity = qtc.compare_texts(user_input, full_text)
            
            # Consolidate error details in a single object
            error_info = {
                'input_text': user_input,
                'correct_text': full_text,
                'differences': differences,
                'similarity': similarity,
                'timestamp': datetime.now().strftime("%H:%M:%S")
            }
            session['errors'] = [error_info]
            session['total_similarity'] = similarity
            session['verses_attempted'] = 1
            return redirect(url_for('report'))
        else:
            error_message = "⚠️ Empty input, please provide your recitation."
            return render_template('recite.html', 
                                 surah=surah, 
                                 full_text=full_text, 
                                 error_message=error_message)
    
    return render_template('recite.html', surah=surah, full_text=full_text)

@app.route('/report')
def report():
    if 'surah' not in session:
        return redirect(url_for('index'))
        
    # Check if we have a final analysis from real-time session
    final_analysis = session.get('final_analysis')
    if final_analysis:
        return render_template('report.html', 
                             analysis=final_analysis,
                             surah=session['surah'],
                             transcript=session.get('final_transcript', ''))
    
    # Fallback to traditional error reporting
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

@app.route('/reset_session', methods=['POST'])
def reset_session():
    """Reset the current session for a new recitation"""
    keys_to_keep = ['surah', 'full_text']
    keys_to_reset = ['current_position', 'realtime_errors', 'errors', 'final_analysis', 'final_transcript']
    
    for key in keys_to_reset:
        session.pop(key, None)
    
    session['current_position'] = 0
    session['total_similarity'] = 0.0
    session['verses_attempted'] = 0
    
    return jsonify({'status': 'reset_complete', 'message': 'Enhanced Arabic processing ready'})

@app.route('/test_normalization', methods=['GET'])
def test_normalization():
    """Test endpoint to verify Arabic normalization is working"""
    test_cases = [
        'الله',  # Should normalize to same as ٱلله
        'ٱلله',  # Hamzat Al-Wasl version
        'الرحمن',  # Should normalize to same as ٱلرحمن  
        'ٱلرحمن',  # Hamzat Al-Wasl version
        'الرحيم',  # Should normalize to same as ٱلرحیم
        'ٱلرحیم'   # Hamzat Al-Wasl version
    ]
    
    results = {}
    for text in test_cases:
        normalized = qtc.normalize_arabic_text(text)
        results[text] = {
            'original': text,
            'normalized': normalized,
            'length': len(text),
            'normalized_length': len(normalized)
        }
    
    # Test comparisons
    comparisons = [
        ('الله', 'ٱلله'),
        ('الرحمن', 'ٱلرحمن'),
        ('الرحيم', 'ٱلرحیم')
    ]
    
    comparison_results = {}
    for word1, word2 in comparisons:
        is_similar, similarity = qtc.advanced_word_comparison(word1, word2)
        comparison_results[f"{word1} vs {word2}"] = {
            'is_similar': is_similar,
            'similarity': similarity,
            'word1_normalized': qtc.normalize_arabic_text(word1),
            'word2_normalized': qtc.normalize_arabic_text(word2)
        }
    
    return jsonify({
        'normalizations': results,
        'comparisons': comparison_results,
        'status': 'Enhanced Arabic processing active'
    })

@app.errorhandler(404)
def not_found_error(error):
    return "Page not found", 404

@app.errorhandler(500)
def internal_error(error):
    return "Internal server error", 500

if __name__ == "__main__":
    print("🕌 Quran Recitation Checker with Enhanced Arabic Processing")
    print("🔤 Hamzat Al-Wasl (ٱ) normalization enabled")
    print("🚀 Starting server...")
    app.run(debug=True, host='0.0.0.0', port=5000)