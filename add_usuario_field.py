"""
Script para agregar el campo 'usuario' a todas las tablas principales
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

# Tablas a las que se agregará el campo usuario
TABLAS = [
    'pacientes',
    'turnos_turno',
    'turnos_agenda',
    'turnos_cupo',
    'turnos_capacidaddia',
    'turnos_weeklyavailability',
    'turnos_turnomensual',
    'turnos_coordinados',
    'determinaciones',
    'perfiles',
    'medicos'
]

def add_usuario_field():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("Conectado a la base de datos PostgreSQL")
        print("Agregando campo 'usuario' a las tablas...\n")
        
        for tabla in TABLAS:
            # Verificar si la columna ya existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name=%s AND column_name='usuario'
            """, (tabla,))
            
            if cursor.fetchone():
                print(f"⚠️  {tabla}: La columna 'usuario' ya existe")
            else:
                # Agregar columna usuario
                cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN usuario VARCHAR(150)")
                conn.commit()
                print(f"✅ {tabla}: Columna 'usuario' agregada")
        
        cursor.close()
        conn.close()
        print("\n✅ Proceso completado exitosamente")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

if __name__ == '__main__':
    add_usuario_field()
