import psycopg2
import csv

# Configuración de la base de datos
DB_CONFIG = {
    'dbname': 'Laboratorio',
    'user': 'postgres',
    'password': 'estufa10',
    'host': 'localhost',
    'port': '5432'
}

def import_perfiles():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        # Eliminar todos los perfiles existentes
        cursor.execute("DELETE FROM perfiles")
        deleted_count = cursor.rowcount
        print(f"✅ Eliminados {deleted_count} perfiles existentes")
        
        # Leer el CSV
        csv_path = r'c:\Users\mauro\Downloads\perfiles - Hoja 1.csv'
        with open(csv_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            
            imported = 0
            for row in csv_reader:
                codigo = row['codigo'].strip()
                nombre = row['nombre perfil'].strip()
                determinaciones = row['determinaciones'].strip()
                
                # Insertar el perfil
                cursor.execute("""
                    INSERT INTO perfiles (codigo, nombre, determinaciones, usuario)
                    VALUES (%s, %s, %s, %s)
                """, (codigo, nombre, determinaciones, 'SYSTEM'))
                
                imported += 1
            
            conn.commit()
            print(f"✅ Importados {imported} perfiles nuevos")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    import_perfiles()
