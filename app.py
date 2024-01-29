from flask import Flask, render_template, request, redirect, url_for
import uuid
import os
import time
import csv
import rasterio
import numpy as np
from rasterio.plot import reshape_as_image
from skimage import exposure

app = Flask(__name__)

class ImageEditor:
    def __init__(self):
        self.users = []
        self.current_user = None
        self.selected_tiff = None
        self.folder_path = None
        self.comments_file = 'comments.csv'  # File to store comments
        self.edits_file = 'user_edits.csv'  # File to store user edits

    def create_random_users(self, n):
        user_types = ['Admin', 'Analyst', 'Interpreter']
        for i in range(1, n + 1):
            for user_type in user_types:
                user_id = str(uuid.uuid4())
                user_name = f"{user_type}{i}"
                self.users.append({'id': user_id, 'name': user_name})

    def select_user(self, user_choice):
        if 0 <= user_choice < len(self.users):
            self.current_user = self.users[user_choice]
            return True
        else:
            return False

    def input_tiff_folder(self, folder_path):
        if os.path.exists(folder_path):
            tiff_files = [f for f in os.listdir(folder_path) if f.endswith('.tif') or f.endswith('.tiff')]

            for tiff_file in tiff_files:
                tiff_path = os.path.join(folder_path, tiff_file)
                metadata = self.get_tiff_metadata(tiff_path)
                print(f"Metadata for {tiff_file}: {metadata}")

            self.folder_path = folder_path
            return True, tiff_files
        else:
            return False, []

    def get_tiff_metadata(self, tiff_file):
        with rasterio.open(tiff_file) as dataset:
            metadata = dataset.meta
        return metadata

    def select_tiff_for_analysis(self, selected_tiff):
        self.selected_tiff = selected_tiff

    def perform_analysis(self, input_tiff_path, output_tiff_path, analysis_type):
        with rasterio.open(input_tiff_path) as dataset:
            image = dataset.read()

            if analysis_type == 'histogram_equalization':
                equalized_image = np.zeros_like(image)
                for band in range(image.shape[0]):
                    equalized_image[band] = exposure.equalize_hist(image[band])

                with rasterio.open(output_tiff_path, 'w', **dataset.meta) as output_dataset:
                    output_dataset.write(equalized_image)

    def get_output_tiff_path(self):
        if self.selected_tiff:
            return os.path.join('data', f"usea_{self.selected_tiff}")

    def save_comment(self, user_type, selected_image, comment):
        with open(self.comments_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([user_type, selected_image, comment])

    def save_edit(self, user_type, action):
        with open(self.edits_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([user_type, action, time.strftime('%Y-%m-%d %H:%M:%S')])

image_editor = ImageEditor()

@app.route('/')
def index():
    return render_template('index.html', users=image_editor.users)

@app.route('/select_user', methods=['POST'])
def select_user():
    user_choice = int(request.form['user'])
    if image_editor.select_user(user_choice):
        return redirect(url_for('input_tiff_folder'))
    else:
        return "Invalid user selection."

@app.route('/input_tiff_folder')
def input_tiff_folder():
    return render_template('input_tiff_folder.html')

@app.route('/process_tiff_folder', methods=['POST'])
def process_tiff_folder():
    folder_path = request.form['folder_path']
    success, tiff_files = image_editor.input_tiff_folder(folder_path)

    if success:
        return render_template('select_tiff.html', tiff_files=tiff_files, folder_path=folder_path)
    else:
        return "Invalid folder path. Please provide a valid local folder path."

@app.route('/select_tiff_for_analysis', methods=['POST'])
def select_tiff_for_analysis():
    selected_tiff = request.form['selected_tiff']
    image_editor.select_tiff_for_analysis(selected_tiff)

    folder_path = request.form['folder_path']
    tiff_path = os.path.join(folder_path, selected_tiff)
    metadata = image_editor.get_tiff_metadata(tiff_path)

    return render_template('choose_analysis.html', selected_tiff=selected_tiff, metadata=metadata)

@app.route('/choose_analysis', methods=['POST'])
def choose_analysis():
    selected_tiff = request.form['selected_tiff']
    analysis_type = request.form['analysis_type']

    if image_editor.current_user['name'].startswith('Interpreter'):
        # For Interpreter, ask for the single TIFF path
        return render_template('interpret_tiff_path.html', selected_tiff=selected_tiff, analysis_type=analysis_type)
    else:
        # For Admin or Analyst, ask for the TIFF folder path
        return render_template('confirm_analysis.html', selected_tiff=selected_tiff, analysis_type=analysis_type)

@app.route('/confirm_analysis', methods=['POST'])
def confirm_analysis():
    selected_tiff = request.form['selected_tiff']
    analysis_type = request.form['analysis_type']
    input_tiff_path = os.path.join(image_editor.folder_path, selected_tiff)
    output_tiff_path = image_editor.get_output_tiff_path()

    return render_template('confirm_analysis.html', selected_tiff=selected_tiff, analysis_type=analysis_type, input_tiff_path=input_tiff_path, output_tiff_path=output_tiff_path)

@app.route('/execute_analysis', methods=['POST'])
def execute_analysis():
    user_choice = request.form.get('confirm_analysis', 'No')
    selected_tiff = request.form.get('selected_tiff')
    analysis_type = request.form.get('analysis_type')

    if user_choice == 'Yes':
        action_message = None
        if image_editor.current_user['name'].startswith('Interpreter'):
            action_message = "Interpreter analysis executed."
        elif image_editor.current_user['name'].startswith(('Admin', 'Analyst')):
            input_tiff_path = os.path.join(image_editor.folder_path, selected_tiff)
            output_tiff_path = image_editor.get_output_tiff_path()
            image_editor.perform_analysis(input_tiff_path, output_tiff_path, analysis_type)
            action_message = f"Analysis completed. Output saved to '{output_tiff_path}'."

        # Save user edit information
        image_editor.save_edit(image_editor.current_user['name'], action_message)

        return action_message
    else:
        return "Analysis canceled by the user."
    
@app.route('/execute_interpreter_analysis', methods=['POST'])
def execute_interpreter_analysis():
    selected_tiff = request.form.get('selected_tiff')
    analysis_type = request.form.get('analysis_type')

    # Implement interpreter-specific analysis logic here
    # For now, let's print a message
    print(f"Interpreter analysis executed for {selected_tiff}. Analysis type: {analysis_type}")

    return f"Interpreter analysis completed for {selected_tiff}. Analysis type: {analysis_type}"

@app.route('/view_analyzed_images')
def view_analyzed_images():
    if image_editor.current_user['name'].startswith('Interpreter'):
        analyzed_images = os.listdir('analyzed_images_folder')
        return render_template('interpreter_dashboard.html', analyzed_images=analyzed_images)
    else:
        return "User not authorized to access the interpreter dashboard."

@app.route('/interpreter_comments', methods=['POST'])
def interpreter_comments():
    if image_editor.current_user['name'].startswith('Interpreter'):
        selected_image = request.form.get('selected_image')
        comment = request.form.get('comment')
        image_editor.save_comment('Interpreter', selected_image, comment)
        return f"Comment saved for {selected_image}."
    else:
        return "User not authorized to submit comments."

@app.route('/admin_analyst_edits', methods=['POST'])
def admin_analyst_edits():
    if image_editor.current_user['name'].startswith(('Admin', 'Analyst')):
        selected_image = request.form.get('selected_image')
        edit_type = request.form.get('edit_type')
        image_editor.save_comment('Admin/Analyst', selected_image, edit_type)
        return f"Edit type saved for {selected_image}."
    else:
        return "User not authorized to perform edits."

if __name__ == '__main__':
    image_editor.create_random_users(2)
    app.run(debug=True)
