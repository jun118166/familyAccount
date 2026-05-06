from flask import Flask, request, jsonify, render_template
from datetime import datetime
import os
import json

app = Flask(__name__)

# 使用环境变量存储数据（用于演示，实际部署应使用 Vercel KV）
# 在 Vercel 生产环境中，请使用 @vercel/kv
TRANSACTIONS_KEY = "finance_transactions"

# 模拟内存存储（用于开发测试）
_memory_store = {}

def get_transactions_from_store():
    try:
        # 尝试使用 Vercel KV
        from vercel.kv import get, set
        data = get(TRANSACTIONS_KEY)
        if data:
            return json.loads(data)
        return []
    except ImportError:
        # 回退到内存存储
        return _memory_store.get(TRANSACTIONS_KEY, [])

def save_transactions_to_store(transactions):
    try:
        # 尝试使用 Vercel KV
        from vercel.kv import set
        set(TRANSACTIONS_KEY, json.dumps(transactions))
    except ImportError:
        # 回退到内存存储
        _memory_store[TRANSACTIONS_KEY] = transactions

# API 端点

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    try:
        transactions = get_transactions_from_store()
        transactions.sort(key=lambda x: (x['date'], x['created_at']), reverse=True)
        return jsonify({'success': True, 'data': transactions})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/transactions', methods=['POST'])
def add_transaction():
    try:
        data = request.get_json()
        transactions = get_transactions_from_store()
        
        new_id = max([t['id'] for t in transactions], default=0) + 1
        new_transaction = {
            'id': new_id,
            'date': data['date'],
            'description': data['description'],
            'category': data['category'],
            'amount': float(data['amount']),
            'type': data['type'],
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        transactions.append(new_transaction)
        save_transactions_to_store(transactions)
        
        return jsonify({'success': True, 'message': '记录添加成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/transactions/<int:id>', methods=['PUT'])
def update_transaction(id):
    try:
        data = request.get_json()
        transactions = get_transactions_from_store()
        
        for t in transactions:
            if t['id'] == id:
                t['date'] = data['date']
                t['description'] = data['description']
                t['category'] = data['category']
                t['amount'] = float(data['amount'])
                t['type'] = data['type']
                break
        
        save_transactions_to_store(transactions)
        return jsonify({'success': True, 'message': '记录更新成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/transactions/<int:id>', methods=['DELETE'])
def delete_transaction(id):
    try:
        transactions = get_transactions_from_store()
        transactions = [t for t in transactions if t['id'] != id]
        save_transactions_to_store(transactions)
        return jsonify({'success': True, 'message': '记录删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    try:
        transactions = get_transactions_from_store()
        
        total_income = sum(t['amount'] for t in transactions if t['type'] == 'income')
        total_expense = sum(t['amount'] for t in transactions if t['type'] == 'expense')
        
        expense_by_category = {}
        for t in transactions:
            if t['type'] == 'expense':
                expense_by_category[t['category']] = expense_by_category.get(t['category'], 0) + t['amount']
        
        categories = list(expense_by_category.keys())
        amounts = list(expense_by_category.values())
        
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

# Vercel 部署需要的应用对象
application = app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)