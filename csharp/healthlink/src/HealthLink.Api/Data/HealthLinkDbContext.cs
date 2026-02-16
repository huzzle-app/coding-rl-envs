using HealthLink.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace HealthLink.Api.Data;

public class HealthLinkDbContext : DbContext
{
    public HealthLinkDbContext(DbContextOptions<HealthLinkDbContext> options)
        : base(options)
    {
    }

    public DbSet<Patient> Patients => Set<Patient>();
    public DbSet<Appointment> Appointments => Set<Appointment>();
    public DbSet<AppointmentNote> AppointmentNotes => Set<AppointmentNote>();
    public DbSet<PatientDocument> PatientDocuments => Set<PatientDocument>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        modelBuilder.Entity<Patient>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.Name);
            entity.Property(e => e.Email);
            entity.Property(e => e.NormalizedName);

            entity.HasMany(e => e.Appointments)
                .WithOne(a => a.Patient)
                .HasForeignKey(a => a.PatientId);

            entity.HasMany(e => e.Documents)
                .WithOne(d => d.Patient)
                .HasForeignKey(d => d.PatientId);
        });

        modelBuilder.Entity<Appointment>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.DateTime);
            entity.Property(e => e.Status);
            entity.ComplexProperty(e => e.Slot);

            entity.HasMany(e => e.Notes)
                .WithOne(n => n.Appointment)
                .HasForeignKey(n => n.AppointmentId);
        });

        modelBuilder.Entity<AppointmentNote>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.Content);
        });

        modelBuilder.Entity<PatientDocument>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.FileName);
            entity.Property(e => e.ContentType);
        });
    }
}
