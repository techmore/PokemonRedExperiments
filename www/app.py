from flask import Flask, request, jsonify, send_from_directory, render_template
import os
import datetime
import json

app = Flask(__name__, static_folder="static")

app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB limit
app.config['UPLOAD_FOLDER'] = './uploads/'
app.config['METADATA_FILE'] = './uploads/metadata.txt'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def read_metadata():
    if os.path.exists(app.config['METADATA_FILE']):
        with open(app.config['METADATA_FILE'], 'r') as f:
            return json.load(f)
    else:
        return []

def write_metadata(data):
    with open(app.config['METADATA_FILE'], 'w') as f:
        json.dump(data, f)

@app.route('/')
def root():
    files_data = read_metadata()
    files_data.sort(key=lambda x: x['steps'], reverse=True)
    return render_template('index.html', files=files_data)

@app.route('/upload', methods=['POST'])
def upload_file():
    files_data = read_metadata()
    
    uploaded_file = request.files.get('file')
    steps = request.form.get('steps')
    if uploaded_file and steps:
        try:
            steps = int(steps)
        except ValueError:
            return jsonify({'error': 'Invalid steps value'}), 400

        filename = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)

        # Check for duplicate filenames
        existing_files = [f['filename'] for f in files_data]
        if filename in existing_files:
            return jsonify({'error': 'Duplicate file detected'}), 400

        uploaded_file.save(filename)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        file_info = {'filename': uploaded_file.filename, 'filepath': filename, 'steps': steps, 'timestamp': timestamp}
        files_data.append(file_info)

        files_data.sort(key=lambda x: x['steps'], reverse=True)
        write_metadata(files_data)
        
        return jsonify({'success': True, 'files': files_data})
    else:
        return jsonify({'error': 'Missing file or steps'}), 400

if __name__ == '__main__':
    app.run(debug=True)

