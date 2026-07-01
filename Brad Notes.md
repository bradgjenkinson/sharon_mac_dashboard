- to run the streamlit app in your browser, comment out the pyodide_http.patch_all() line in app.py

To push this to a Mac App:
1. Open your web browser and go to your GitHub repository.
2. Click on the Actions tab at the top.
3. You will see a running workflow named "Build macOS Desktop App". Click on it to see the live logs.
4. Once the job finishes successfully (turning green), scroll down to the bottom of the page to find the Artifacts section.
5. Click on macOS-Desktop-App to download the zipped installer, which you can then send directly to your friend.