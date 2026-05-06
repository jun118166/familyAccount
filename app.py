from flask import Flask, request, jsonify, render_template, make_response
from datetime import datetime
import os
import sqlite3
import csv
import io
import tempfile

app = Flask(__name__)

# SQLite 配置 - 使用系统临时目录（跨平台兼容）
# 注意：临时目录在 Vercel Serverless 环境中是可写的，但数据不会持久化
# 每次部署或冷启动后数据会丢失
DATABASE = os.path.join(tempfile.gettempdir(), 'finance.db')

# 获取数据库连接
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# 初始化数据库表
def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# API 端点

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM transactions ORDER BY date DESC, created_at DESC')
        transactions = cursor.fetchall()
        conn.close()
        
        result = []
        for row in transactions:
            result.append({
                'id': row['id'],
                'date': row['date'],
                'description': row['description'],
                'category': row['category'],
                'amount': float(row['amount']),
                'type': row['type'],
                'created_at': row['created_at']
            })
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/transactions', methods=['POST'])
def add_transaction():
    try:
        data = request.get_json()
        date = data['date']
        description = data['description']
        category = data['category']
        amount = data['amount']
        type_ = data['type']
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO transactions (date, description, category, amount, type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (date, description, category, amount, type_, created_at))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '记录添加成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/transactions/<int:id>', methods=['PUT'])
def update_transaction(id):
    try:
        data = request.get_json()
        date = data['date']
        description = data['description']
        category = data['category']
        amount = data['amount']
        type_ = data['type']
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE transactions 
            SET date=?, description=?, category=?, amount=?, type=?
            WHERE id=?
        ''', (date, description, category, amount, type_, id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '记录更新成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/transactions/<int:id>', methods=['DELETE'])
def delete_transaction(id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM transactions WHERE id=?', (id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '记录删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # 总收入
        cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type="income"')
        total_income = cursor.fetchone()[0] or 0.0
        
        # 总支出
        cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type="expense"')
        total_expense = cursor.fetchone()[0] or 0.0
        
        # 支出分类统计
        cursor.execute('''
            SELECT category, SUM(amount) 
            FROM transactions 
            WHERE type="expense" 
            GROUP BY category
        ''')
        expense_by_category = cursor.fetchall()
        
        conn.close()
        
        categories = []
        amounts = []
        for row in expense_by_category:
            categories.append(row['category'])
            amounts.append(float(row['SUM(amount)']))
        
        return jsonify({
            'success': True,
            'data': {
                'total_income': float(total_income),
                'total_expense': float(total_expense),
                'balance': float(total_income) - float(total_expense),
                'expense_categories': categories,
                'expense_amounts': amounts
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# 导出数据为 CSV
@app.route('/api/export', methods=['GET'])
def export_transactions():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM transactions ORDER BY date DESC, created_at DESC')
        transactions = cursor.fetchall()
        conn.close()
        
        output = io.StringIO()
        writer = csv.writer(output)
        # 写入表头
        writer.writerow(['日期', '描述', '分类', '金额', '类型'])
        # 写入数据
        for row in transactions:
            type_text = '收入' if row['type'] == 'income' else '支出'
            writer.writerow([
                row['date'],
                row['description'],
                row['category'],
                row['amount'],
                type_text
            ])
        
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=transactions_{datetime.now().strftime("%Y%m%d")}.csv'
        return response
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# 导入 CSV 数据
@app.route('/api/import', methods=['POST'])
def import_transactions():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '请选择要导入的文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '请选择要导入的文件'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'success': False, 'message': '只支持 CSV 文件'}), 400
        
        content = file.read().decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        
        if len(rows) <= 1:
            return jsonify({'success': False, 'message': '文件内容为空'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        imported_count = 0
        
        for i, row in enumerate(rows[1:], start=2):  # 跳过表头
            if len(row) < 5:
                continue
            
            try:
                date = row[0].strip()
                description = row[1].strip()
                category = row[2].strip()
                amount = float(row[3].strip())
                type_text = row[4].strip()
                
                if type_text == '收入':
                    type_ = 'income'
                elif type_text == '支出':
                    type_ = 'expense'
                else:
                    continue
                
                if date and category and amount > 0:
                    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('''
                        INSERT INTO transactions (date, description, category, amount, type, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (date, description, category, amount, type_, created_at))
                    imported_count += 1
            except Exception as e:
                continue
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': f'成功导入 {imported_count} 条记录'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# 下载导入模板
@app.route('/api/import/template', methods=['GET'])
def download_template():
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        # 写入表头
        writer.writerow(['日期', '描述', '分类', '金额', '类型'])
        # 写入示例数据
        writer.writerow(['2024-01-15', '工资收入', '工资', '8000', '收入'])
        writer.writerow(['2024-01-15', '午餐', '餐饮', '35', '支出'])
        writer.writerow(['2024-01-16', '地铁充值', '交通', '100', '支出'])
        writer.writerow(['2024-01-17', '购物', '购物', '200', '支出'])
        
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = 'attachment; filename=import_template.csv'
        return response
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Vercel 部署需要的应用对象
application = app

# 初始化数据库（在模块加载时执行）
init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)