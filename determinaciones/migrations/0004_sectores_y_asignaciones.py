from django.db import migrations

SECTORES = [
    "Hematologia",
    "Quimica",
    "Endocrinologia",
    "Serologia",
    "Guardia",
    "Enzimas Cardiacas",
    "Biologia Molecular",
]

HEMATOLOGIA_CODIGOS = [
    "1000", "1010", "1015", "1040", "1130", "1140", "1145",
    "1500", "1505", "1510", "1515", "1520",
]
QUIMICA_CODIGOS = [
    "2000", "2005", "2010", "2015", "2020", "2025", "2030", "2035", "2040",
    "2045", "2050", "2055", "2065", "2070", "2075", "2080", "2085", "2090",
    "2095", "2100", "2115", "2120", "2125", "2130", "2135", "2140", "2145",
    "2160", "2165", "2170", "2175", "2180", "2185", "2190", "2195", "2200",
    "2205", "2210", "2215", "2220", "2265",
    "2500", "2505", "2510", "2515", "2520", "2525", "2530", "2535", "2540",
    "2545", "2550", "2555", "2914",
    "4004", "4006", "4008", "4010", "4012",
]
ENDOCRINOLOGIA_CODIGOS = [
    "3000", "3005", "3010", "3015", "3020", "3035", "3040", "3055",
    "3085", "3090", "3095", "3105", "3120", "3150", "3155", "3160", "3165",
    "3175", "3176", "3180", "3185", "3190", "3195", "3200", "3205", "3210",
    "3220", "3225", "3230", "3235", "3240", "3245", "3250", "3255",
    "3260", "3265", "3270",
]
SEROLOGIA_CODIGOS = [
    "3110", "3115", "3125", "3130", "3135", "3145", "3170",
    "3400", "3405", "3410", "3415", "3430", "3435", "3440", "3465",
    "3500", "3505", "3510", "3515", "3520", "3525", "3530", "3535",
    "3540", "3545", "3550", "3555", "3560", "3565", "3570", "3575",
    "3580", "3585", "3590", "3595", "3615",
    "6000", "6005", "6010", "6015", "6020", "6025", "6030", "6035", "6040",
    "6045", "6050", "6055", "6060", "6065", "6070", "6075", "6080", "6085",
    "7005",
]
ENZIMAS_CODIGOS = [
    "2060",
    "5000", "5005", "5010", "5015", "5020", "5025", "5030",
    "5035", "5040", "5045", "5050", "5055", "5060", "5065",
    "5070", "5075", "5080",
]

HEMATOLOGIA_COMPLEJAS = ["/171", "/475", "/476"]
QUIMICA_COMPLEJAS = [
    "/110", "/413", "/481", "/546", "/555", "/711", "/712", "/717",
    "/736", "/764", "/850", "/852", "/854", "/856", "/858", "/860",
    "/862", "/864", "/866", "/868", "/870", "/872", "/873", "/874",
    "/900", "/902", "/904", "/906", "/908",
]
ENDOCRINOLOGIA_COMPLEJAS = [
    "/1070", "/305", "/310", "/311", "/315", "/320", "/330", "/335", "/340",
]
SEROLOGIA_COMPLEJAS = [
    "/063", "/350", "/352", "/354", "/356", "/358", "/360", "/362", "/364",
    "/366", "/368", "/370", "/372", "/374", "/376", "/378", "/380", "/382",
    "/390", "/934", "/936",
]
ENZIMAS_COMPLEJAS = ["/404", "/405"]


def crear_sectores_y_asignar(apps, schema_editor):
    Determinacion = apps.get_model("determinaciones", "Determinacion")
    DeterminacionCompleja = apps.get_model("determinaciones", "DeterminacionCompleja")
    Sector = apps.get_model("determinaciones", "Sector")

    for nombre in SECTORES:
        Sector.objects.get_or_create(nombre=nombre)

    hem = Sector.objects.get(nombre="Hematologia")
    qui = Sector.objects.get(nombre="Quimica")
    end = Sector.objects.get(nombre="Endocrinologia")
    ser = Sector.objects.get(nombre="Serologia")
    enz = Sector.objects.get(nombre="Enzimas Cardiacas")

    Determinacion.objects.filter(codigo__in=HEMATOLOGIA_CODIGOS).update(sector=hem)
    Determinacion.objects.filter(codigo__in=QUIMICA_CODIGOS).update(sector=qui)
    Determinacion.objects.filter(codigo__in=ENDOCRINOLOGIA_CODIGOS).update(sector=end)
    Determinacion.objects.filter(codigo__in=SEROLOGIA_CODIGOS).update(sector=ser)
    Determinacion.objects.filter(codigo__in=ENZIMAS_CODIGOS).update(sector=enz)

    DeterminacionCompleja.objects.filter(codigo__in=HEMATOLOGIA_COMPLEJAS).update(sector=hem)
    DeterminacionCompleja.objects.filter(codigo__in=QUIMICA_COMPLEJAS).update(sector=qui)
    DeterminacionCompleja.objects.filter(codigo__in=ENDOCRINOLOGIA_COMPLEJAS).update(sector=end)
    DeterminacionCompleja.objects.filter(codigo__in=SEROLOGIA_COMPLEJAS).update(sector=ser)
    DeterminacionCompleja.objects.filter(codigo__in=ENZIMAS_COMPLEJAS).update(sector=enz)


def revertir(apps, schema_editor):
    Determinacion = apps.get_model("determinaciones", "Determinacion")
    DeterminacionCompleja = apps.get_model("determinaciones", "DeterminacionCompleja")
    Determinacion.objects.all().update(sector=None)
    DeterminacionCompleja.objects.all().update(sector=None)
    apps.get_model("determinaciones", "Sector").objects.filter(nombre__in=SECTORES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('determinaciones', '0003_sector_alter_determinacion_options_and_more'),
    ]

    operations = [
        migrations.RunPython(crear_sectores_y_asignar, revertir),
    ]
