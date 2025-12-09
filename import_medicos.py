"""
Script para crear la tabla medicos e importar los datos desde el CSV
"""
import psycopg2
import csv

# Configuración de conexión
DB_CONFIG = {
    'dbname': 'Laboratorio',
    'user': 'postgres',
    'password': 'estufa10',
    'host': 'localhost',
    'port': '5432'
}

CSV_FILE = r"c:\Users\mauro\Downloads\Hoja de cálculo sin título - Hoja 1.csv"

def create_table_and_import():
    try:
        # Conectar a la base de datos
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("Conectado a la base de datos PostgreSQL")
        
        # Eliminar tabla si existe (para reiniciar)
        cursor.execute("DROP TABLE IF EXISTS medicos;")
        print("✅ Tabla anterior eliminada (si existía)")
        
        # Crear tabla medicos
        cursor.execute("""
            CREATE TABLE medicos (
                id SERIAL PRIMARY KEY,
                matricula_provincial INTEGER NOT NULL,
                nombre_apellido VARCHAR(200) NOT NULL,
                creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print("✅ Tabla 'medicos' creada exitosamente")
        
        # Leer CSV e importar datos
        with open(CSV_FILE, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            contador = 0
            
            for row in csv_reader:
                try:
                    # Limpiar espacios en blanco
                    matricula = row['Matrícula Provincial'].strip()
                    medico = row['Medico'].strip()
                    
                    if matricula and medico:
                        cursor.execute("""
                            INSERT INTO medicos (matricula_provincial, nombre_apellido)
                            VALUES (%s, %s)
                        """, (int(matricula), medico))
                        contador += 1
                except Exception as e:
                    print(f"⚠️  Error al procesar fila: {row} - {e}")
                    continue
            
            conn.commit()
            print(f"✅ {contador} médicos importados exitosamente")
        
        # Mostrar algunos registros de ejemplo
        cursor.execute("SELECT * FROM medicos ORDER BY nombre_apellido LIMIT 10;")
        print("\n📋 Primeros 10 médicos (ordenados alfabéticamente):")
        print("-" * 70)
        for row in cursor.fetchall():
            print(f"  ID: {row[0]} | Matrícula: {row[1]} | Nombre: {row[2]}")
        print("-" * 70)
        
        # Mostrar total de registros
        cursor.execute("SELECT COUNT(*) FROM medicos;")
        total = cursor.fetchone()[0]
        print(f"\n📊 Total de médicos en la base de datos: {total}")
        
        cursor.close()
        conn.close()
        print("\n✅ Operación completada exitosamente")
        
    except FileNotFoundError:
        print(f"❌ Error: No se encontró el archivo CSV: {CSV_FILE}")
    except psycopg2.Error as e:
        print(f"❌ Error de PostgreSQL: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    create_table_and_import()
