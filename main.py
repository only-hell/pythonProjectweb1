from flask_login import LoginManager, login_user, login_required, logout_user
from collections import namedtuple
import re
import pymorphy2
from flask import current_app, abort
import docx
import os
import sqlite3
from flask import Flask, render_template, redirect, url_for, request
from data import db_session
from data.login_form import LoginForm
from data.users import User
from data.register import RegisterForm

app = Flask(__name__)
app.config['SECRET_KEY'] = 'textmanager_secret_key'

login_manager = LoginManager()
login_manager.init_app(app)
Message = namedtuple('Message', 'text')
text_output = []
text_to_file = []
type_texts = []

# различные проверки безопасности файла
# проверка того, что обьем файла не более 1мб
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
# допустимые расширения файлов
app.config['UPLOAD_EXTENSIONS'] = ['.doc', '.docx']
app.config['UPLOAD_PATH'] = 'uploads'


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


@app.route('/base', methods=['GET'])
def base():
    return render_template('base.html', messages=text_output, type_text=type_texts)


@app.route('/add_type_text', methods=['POST'])
def add_type_text():
    type_text = request.form['type_text']
    type_texts.clear()
    type_texts.append(type_text)
    return redirect(url_for('base'))


@app.route('/add_text', methods=['POST'])
def add_text():
    question = request.form['question']
    number = request.form['number']
    if type_texts == ['text']:
        text = request.form['text']

    elif type_texts == ['file']:
        uploaded_file = request.files['file']
        file = uploaded_file.filename
        print(uploaded_file)

        if file != '':
            # С помощью этой логики на любые имена файлов, которые не имеют
            # одного из утвержденных расширений файлов, будет выдано сообщение об ошибке 400
            file_ext = os.path.splitext(file)[1]
            if file_ext not in current_app.config['UPLOAD_EXTENSIONS']:
                abort(400)
            else:
                if str(file).find("doc") != -1:
                    doc = docx.Document(file)
                    texts = []
                    for paragraph in doc.paragraphs:
                        texts.append(paragraph.text)
                    text = '\n'.join(texts)

    text_output.clear()
    morph = pymorphy2.MorphAnalyzer()
    text = text.replace(',', '')
    a = []
    b = []
    c = [text, question]
    analysis_text = []
    analysis_question = []
    analysis_question1 = []
    suggestions = []
    """разбиение введенного текста для анализа
    и текста вопроса на предложения и слова путем создания вложенных списков"""
    split_regex = re.compile(r'[.|!|?|…]')
    for i in c:
        sentences = filter(lambda t: t, [t.strip() for t in split_regex.split(i)])
        for s in sentences:
            """создание списка с предложениями для
            дальнейшего вывода слов в той форме в которой они были изначально"""
            suggestions.append(s)
            g = s.split()
            for t in g:
                res = morph.parse(t)[0]
                """во вложенные списки попадают только те части речи,
                 которые не являются частицами, местоимениями, местоимениями, союзами, предлогами """
                if ("CONJ" not in res.tag) and ("NPRO" not in res.tag) and ("PREP" not in res.tag) and (
                        "PRCL" not in res.tag):
                    """причем слова изменются и попадают в список в начальной форме"""
                    b.append(((morph.parse(t)[0]).normal_form).lower())
                    a.append(b)
                    b = []
            if i == text:
                """вложенный список с текстом для анализа"""
                analysis_text.append(a)
            if i == question:
                """вложенный список с вопросами"""
                """можно будет добавить возможность ввода сразу нескольких вопросов вместо одного"""
                analysis_question1.append(a)
            a = []
    numbers = []
    for i in analysis_question1:
        for j in i:
            analysis_question.append(''.join(j))
    """сравниваются слова из введенного текста и слова из текста вопроса """
    for i in analysis_text:
        for j in i:
            e = ''.join(j)
            for k in analysis_question:
                if k == e:
                    """и добаляются индексы предложений в новый список"""
                    numbers.append(analysis_text.index(i))
                    continue
    numbers1 = []
    for i in numbers:
        """если в предложении и вопросе количество выбранных пользователем слов равно и больше одинаковых слов,
        то индексы этих предложений попадают в новый список """
        if numbers.count(i) >= int(number):
            numbers1.append(i)
    numbers2 = []
    for i in numbers1:
        if i not in numbers2:
            numbers2.append(i)
    for i in numbers2:
        text_output1 = (
            (((str((suggestions[int(i)]))).replace("['", "")).replace("'],", "")).replace("']]", "")).replace(
            "[", "")
        text_output.append(Message(text_output1))
        text_to_file.append(text_output1)

    """запись результатов в файл"""
    f = open("text manager answer.txt", 'w')
    for i in text_to_file:
        f.write(str(i) + '\n')
    f.close()
    print(text_output)
    """добавление предложений в список результатов"""
    return redirect(url_for('base'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(User.email == form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect("/")
        return render_template('login.html', message="Wrong login or password", form=form)
    return render_template('login.html', title='Authorization', form=form)


@app.route("/")
def index():
    db_sess = db_session.create_session()
    users = db_sess.query(User).all()
    names = {name.id: (name.surname, name.name) for name in users}
    return render_template("index.html", names=names, title='Text Manager')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route('/register', methods=['GET', 'POST'])
def reqister():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Register', form=form,
                                   message="Passwords don't match")
        db_sess = db_session.create_session()
        if db_sess.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', title='Register', form=form,
                                   message="This user already exists")
        user = User(
            name=form.name.data,
            surname=form.surname.data,
            email=form.email.data
        )
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        return redirect('/login')
    return render_template('register.html', title='Регистрация', form=form)


def main():
    db_session.global_init("db/text_manager.sqlite")

    app.run()


if __name__ == '__main__':
    main()
