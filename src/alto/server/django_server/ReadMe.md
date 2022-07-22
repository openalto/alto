# Requirements
- Django==4.0.6
- djangorestframework==3.13.1
- requests==2.28.1


# Installation
Install using pip. The `requirements.txt` file is  is under the root directory  of this project.

```text
pip install -r requirements.txt
```
# Usage
In the root directory of the project, there is a `manage.py` file and run the command.
```text
python .\manage.py runserver 0.0.0.0:8000
```
Then you will the information of django server
```text
Watching for file changes with StatReloader
Performing system checks...

System check identified no issues (0 silenced).

You have 18 unapplied migration(s). Your project may not work properly until you apply the migrations for app(s): admin, auth, contenttypes, sessions.
Run 'python manage.py migrate' to apply them.
July 22, 2022 - 15:49:07
Django version 4.0.6, using settings 'altoServer.settings'
Starting development server at http://0.0.0.0:8000/
Quit the server with CTRL-BREAK.
```
> This project does not need to execute the command of 'python manage.py migrate'

# Alto API
```text
http://127.0.0.1:8000/pathvector/pv
```

# Reference

[ The MIME Multipart/Related Content-type](https://www.ietf.org/rfc/rfc2387.txt)

