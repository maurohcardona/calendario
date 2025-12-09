"""
Script para agregar los campos telefono y email a la tabla pacientes
"""
import psycopg2

# Configuración de conexión
DB_CONFIG = {
    'dbname': 'Laboratorio',
    'user': 'postgres',
    'password': 'estufa10',
    'host': 'localhost',
    'port': '5432'
}

def add_fields():
    try:
        # Conectar a la base de datos
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("Conectado a la base de datos PostgreSQL")
        
        # Verificar si la tabla pacientes existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'pacientes'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            print("La tabla 'pacientes' no existe. Creándola...")
            cursor.execute("""
                CREATE TABLE pacientes (
                    id SERIAL PRIMARY KEY,
                    dni VARCHAR(20) UNIQUE NOT NULL,
                    nombre VARCHAR(200) NOT NULL,
                    apellido VARCHAR(200) NOT NULL,
                    fecha_nacimiento DATE,
                    sexo VARCHAR(20),
                    observaciones TEXT,
                    telefono VARCHAR(50),
                    email VARCHAR(100),
                    medico VARCHAR(200),
                    creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            print("✅ Tabla 'pacientes' creada exitosamente con todos los campos")
        else:
            print("La tabla 'pacientes' existe. Agregando campos si no existen...")
            
            # Verificar y agregar campo telefono
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'pacientes' AND column_name = 'telefono';
            """)
            telefono_exists = cursor.fetchone()
            
            if not telefono_exists:
                cursor.execute("ALTER TABLE pacientes ADD COLUMN telefono VARCHAR(50);")
                conn.commit()
                print("✅ Campo 'telefono' agregado exitosamente")
            else:
                print("⚠️  El campo 'telefono' ya existe")
            
            # Verificar y agregar campo email
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'pacientes' AND column_name = 'email';
            """)
            email_exists = cursor.fetchone()
            
            if not email_exists:
                cursor.execute("ALTER TABLE pacientes ADD COLUMN email VARCHAR(100);")
                conn.commit()
                print("✅ Campo 'email' agregado exitosamente")
            else:
                print("⚠️  El campo 'email' ya existe")
            
            # Verificar y agregar campo medico
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'pacientes' AND column_name = 'medico';
            """)
            medico_exists = cursor.fetchone()
            
            if not medico_exists:
                cursor.execute("ALTER TABLE pacientes ADD COLUMN medico VARCHAR(200);")
                conn.commit()
                print("✅ Campo 'medico' agregado exitosamente")
            else:
                print("⚠️  El campo 'medico' ya existe")
        
        # Mostrar estructura de la tabla
        cursor.execute("""
            SELECT column_name, data_type, character_maximum_length 
            FROM information_schema.columns 
            WHERE table_name = 'pacientes'
            ORDER BY ordinal_position;
        """)
        
        print("\n📋 Estructura actual de la tabla 'pacientes':")
        print("-" * 60)
        for row in cursor.fetchall():
            col_name, data_type, max_length = row
            length_info = f"({max_length})" if max_length else ""
            print(f"  • {col_name}: {data_type}{length_info}")
        print("-" * 60)
        
        cursor.close()
        conn.close()
        print("\n✅ Operación completada exitosamente")
        
    except psycopg2.Error as e:
        print(f"❌ Error de PostgreSQL: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    add_fields()
