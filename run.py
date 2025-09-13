from app import create_app

app = create_app()

if __name__ == '__main__':
    app.logger.info("Application starting...")
    app.run(debug=True)
