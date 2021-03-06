from app import app, db
from config import CustomConfig
from controller import check_admin_status
from flask import flash, request, redirect, render_template, url_for, send_file
from flask_login import login_required
from models import *
from controller import get_user_info
from PIL import Image, ImageDraw

import os
import qrcode


def generate_qr_code(schedule_id: str) -> str:
    """
    Функция генерирует qr код в который вшита ссылка для создания нового кабинета
    Пример: http://127.0.0.1/new_schedule/2.18
    qr код сохраняется в папку qrCodes в виде png картинки(Пример такого файла: 'Кабинет: 2.18.png').
    """
    data = f'http://{CustomConfig.SITE_URL}/new_schedule/{schedule_id}'
    file_path = f"qrCodes/Кабинет: {schedule_id}.png"
    img = qrcode.make(data)
    img.save(file_path)

    image = Image.open(file_path)

    drawer = ImageDraw.Draw(image)
    drawer.text((10, 0), f"CABINET: {schedule_id}", fill='black')

    os.remove(file_path)

    image.save(file_path)
    image.show()

    return file_path


@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_index():
    if not check_admin_status():
        flash(f'У вас нет прав для просмотра данной страницы!', 'error')
        app.logger.warning(
            f"Сотрудник с недостаточным уровнем допуска попытался войти в админ-панель: {get_user_info()}")
        return redirect(url_for('index'))
    users = User.query.all()
    cabinets = Cabinet.query.all()
    schedules = ScheduleCleaning.query.all()
    return render_template('admin/index.html', users=users, cabinets=cabinets, schedules=schedules)


@app.route('/logs')
@login_required
def admin_log():
    """
    Функция при GET запросе возвращает страницу страницу где отображаются логи за этот день.
    """
    if not check_admin_status():
        flash(f'У вас нет прав для просмотра данной страницы!', 'error')
        app.logger.warning(
            f"Сотрудник с недостаточным уровнем допуска попытался посмотреть логи: {get_user_info()}")
        return redirect(url_for('index'))
    with open(app.config['LOGFILE'], 'r') as file:
        logs = file.read().split('\n')
        del logs[-1]  # Последним элементом идёт пустая строка
    logs_clear = []
    for key, log in enumerate(logs):
        try:
            _, _, _ = log.split(' | ')  # Проверяет формат, нужно, чтобы не вошёл Traceback
            logs_clear.append(log)
        except ValueError:
            del logs[key]
    flash('Тут только логи за сегодняшний день', 'warning')
    return render_template('admin/log.html', logs=reversed(logs_clear))


@app.route('/work_with_user', methods=['GET', 'POST'])
@login_required
def work_with_user():
    """
    Функция при GET запросе возвращает страницу,
    где в формате таблицы выведена информация о пользователях(ФИО, Почта, Статус Администратора).
    При POST запросе, удаляет пользователя которого выбрал Администратор(Администратора удалить нельзя).
    """
    if not check_admin_status():
        flash(f'У вас нет прав для просмотра данной страницы!', 'error')
        app.logger.warning(
            f"Сотрудник с недостаточным уровнем допуска попытался удалить пользователя: {get_user_info()}")
        return redirect(url_for('index'))
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        user = User.query.filter_by(id=int(user_id))
        user_list = User.query.get(user_id)
        if user.first().admin_status:  # Администратор не может удалить Администратора
            app.logger.warning(
                f'Сотрудник: (id {user_list.id}) {user_list.surname} {user_list.name} {user_list.patronymic}'
                f' попытался удалить Администратора {get_user_info(user)}!')
            flash('Вы не можете удалить этого пользователя!', 'error')
            return redirect(url_for('admin_index'))
        flash(
            f'Сотрудник: (id {user_list.id}) {user_list.surname} {user_list.name} {user_list.patronymic}'
            f' успешно удалён!',
            'success')
        user.delete()
        db.session.commit()
    users = User.query.order_by(User.admin_status.desc()).order_by(User.surname).all()
    return render_template('admin/work_with_user.html', users=users)


@app.route('/admin/new_cabinet_qr/', methods=['POST', 'GET'])
@login_required
def new_cabinet_qr():
    """
    При GET запросе возвращает страницу с выбаром кабинета, для которого сгенерировать qr код.
    При POST запросе, генерирует и сохраняет qr код, возвращает получившийся файл.
    """
    if not check_admin_status():
        flash(f'У вас нет прав для просмотра данной страницы!', 'error')
        app.logger.warning(f"Сотрудник с недостаточным уровнем допуска попытался создать qr код: {get_user_info()}")
        return redirect(url_for('index'))
    if request.method == 'POST':
        cabinet_number = request.form.get('cabinet')
        if not len(cabinet_number.split('.')) == 2:
            flash(f'Номер кабинета должен разделятся точкой(Пример: 1.27)!', 'error')
            return redirect(url_for('index'))
        file_path = generate_qr_code(cabinet_number)
        try:
            return send_file(file_path, as_attachment=True)
        finally:
            os.remove(file_path)
            app.logger.info(f"Создан новый qr код для кабинета: {cabinet_number}. Создал(а): {get_user_info()}")
    cabinets = Cabinet.query.order_by(Cabinet.number).all()
    return render_template('admin/new_cabinet_qr.html', cabinets=cabinets)


@app.route('/admin/new_cabinet', methods=['POST', 'GET'])
@login_required
def new_cabinet():
    """
    При GET запросе возвращает страницу на которой необходимо написать номер кабинета(Номер должен быть разделён точкой,
    пример: 2.18).
    При POST запросе создаёьт кабинет, с указанным пользователем номером.
    """
    if not check_admin_status():
        flash(f'У вас нет прав для просмотра данной страницы!', 'error')
        app.logger.warning(f"Сотрудник с недостаточным уровнем допуска попытался создать кабинет: {get_user_info()}")
        return redirect(url_for('admin_index'))
    if request.method == 'POST':
        cabinet_number = request.form.get('cabinet')
        if not len(cabinet_number.split('.')) == 2:
            flash(f'Номер кабинета должен разделятся точкой(Пример: 1.27)!', 'error')
            return redirect(url_for('admin_index'))
        cabinet = Cabinet(number=cabinet_number)
        db.session.add(cabinet)
        db.session.commit()
        flash(f'Кабинет с номером: {cabinet_number} успешно создан!', 'success')
        app.logger.info(f"Создан новый кабинет: {cabinet_number}. Создал(а): {get_user_info()}")
        return redirect(url_for('admin_index'))
    cabinets = Cabinet.query.order_by(Cabinet.number).all()
    return render_template('admin/new_cabinet.html', cabinets=cabinets)


@app.route('/admin/delete_cabinet', methods=['GET', 'POST'])
@login_required
def delete_cabinet():
    """
    При GET запросе возвращает страницу на которой необходимо выбрать удаляемый кабинет.
    При POST запросе удаляет выбранный Администратором кабинет.
    """
    if not check_admin_status():
        flash(f'У вас нет прав для просмотра данной страницы!', 'error')
        app.logger.warning(f"Сотрудник с недостаточным уровнем допуска попытался создать кабинет: {get_user_info()}")
        return redirect(url_for('index'))
    if request.method == 'POST':
        if not check_admin_status():
            flash(f'У вас нет прав для просмотра данной страницы!', 'error')
            app.logger.warning(
                f"Сотрудник с недостаточным уровнем допуска попытался удалить кабинет: {get_user_info()}")
            return redirect(url_for('index'))
        cabinet_id = request.form.get('cabinet')

        Cabinet.query.filter_by(id=cabinet_id).delete()
        db.session.commit()
        flash(f'Кабинет успешно удалён!', 'success')
        return redirect(url_for('admin_index'))

    cabinets = Cabinet.query.order_by(Cabinet.number).all()
    return render_template('admin/delete_cabinet.html', cabinets=cabinets)

@app.route('/delete_schedule', methods=['GET'])
@login_required
def delete_schedule():
    """
    При GET запросе возвращает страницу для удаления расписания.
    При POST запросе, удаляет выбранное расписани
    (Запрос на удаление идэт с главной страницы(func index), шаблона(template) функция не имеет).
    """
    if not check_admin_status():
        flash(f'У вас нет прав для просмотра данной страницы!', 'error')
        app.logger.warning(f"Сотрудник с недостаточным уровнем допуска попытался удалить расписание: {get_user_info()}")
        return redirect(url_for('index'))
    schedule_id = request.args.get('schedule_id')

    ScheduleCleaning.query.filter_by(id=schedule_id).delete()
    db.session.commit()
    return redirect(url_for('index'))